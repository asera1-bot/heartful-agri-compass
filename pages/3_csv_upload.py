# pages/3_csv_upload.py
from __future__ import annotations

import io
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import require_login
from app.common.constants import DB_PATH
from app.core.db import get_engine, init_db


# =========================
# Page config
# =========================
st.set_page_config(page_title="CSV Upload", layout="wide")
st.title("CSV Upload")
st.caption("収量データCSVをアップロードし、harvest_fact に登録します。")

require_login()
init_db()


# =========================
# Helpers
# =========================
ZEN_NUM = str.maketrans("０１２３４５６７８９．，", "0123456789.,")
EXCEL_EPOCH = datetime(1899, 12, 30)


def get_db_mtime() -> float:
    return DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0


def parse_amount_to_kg(val) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    s = s.translate(ZEN_NUM).replace(",", "")
    s_low = s.lower()

    m = re.search(r"[-+]?\d*\.?\d+", s_low)
    if not m:
        return None

    x = float(m.group())
    return x if "kg" in s_low else x / 1000.0


def parse_harvest_date(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    # Excel serial
    if s.isdigit():
        n = int(s)
        if 30000 <= n <= 60000:
            return (EXCEL_EPOCH + timedelta(days=n)).date().isoformat()

    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass

    dt = pd.to_datetime(s, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.date().isoformat()


def normalize_amount(x: float) -> float:
    return float(round(x, 3))


def ensure_table():
    ddl = """
    CREATE TABLE IF NOT EXISTS harvest_fact (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        harvest_date TEXT NOT NULL,
        company TEXT NOT NULL,
        crop TEXT NOT NULL,
        amount_kg REAL NOT NULL
    );
    """
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)


# =========================
# Status
# =========================
st.caption(f"DB_PATH = {DB_PATH}")
st.caption(f"DB exists = {DB_PATH.exists()}")

engine = get_engine()
try:
    n = pd.read_sql_query("SELECT COUNT(*) AS n FROM harvest_fact", engine)["n"][0]
    st.write("現在の harvest_fact 件数:", int(n))
except Exception:
    st.info("harvest_fact はまだ空です。")


# =========================
# Upload
# =========================
uploaded = st.file_uploader("収量CSVを選択してください", type=["csv"])
if uploaded is None:
    st.stop()

bytes_data = uploaded.getvalue()

# read csv
candidates = [
    ("utf-8-sig", dict(encoding="utf-8-sig", sep=",")),
    ("cp932", dict(encoding="cp932", sep=",")),
    ("cp932_auto", dict(encoding="cp932", sep=None, engine="python")),
]

raw_df = None
for label, params in candidates:
    try:
        raw_df = pd.read_csv(io.BytesIO(bytes_data), **params)
        st.success(f"CSVを読み込みました ({label})")
        break
    except Exception:
        pass

if raw_df is None:
    st.error("CSVを読み込めませんでした。")
    st.stop()


# =========================
# Normalize columns
# =========================
col_map = {
    "収穫日": "harvest_date",
    "日付": "harvest_date",
    "企業名": "company",
    "会社名": "company",
    "作物名": "crop",
    "品目": "crop",
    "収穫量": "amount_g",
    "収穫量(ｇ)": "amount_g",
    "収量(kg)": "amount_kg",
    "収量(㎏)": "amount_kg",
}

df = raw_df.rename(columns={c: col_map.get(str(c).strip(), str(c).strip()) for c in raw_df.columns})

required = {"harvest_date", "company", "crop"}
if not required.issubset(df.columns):
    st.error(f"必須列が不足しています: {required}")
    st.stop()

if "amount_kg" in df.columns:
    df["amount_kg"] = df["amount_kg"].apply(parse_amount_to_kg)
elif "amount_g" in df.columns:
    df["amount_kg"] = df["amount_g"].apply(parse_amount_to_kg)
else:
    st.error("収量列が見つかりません。")
    st.stop()

df["harvest_date"] = df["harvest_date"].apply(parse_harvest_date)
df["company"] = df["company"].astype(str).str.strip()
df["crop"] = df["crop"].astype(str).str.strip()
df["amount_kg"] = df["amount_kg"].apply(lambda x: None if x is None else normalize_amount(x))

df = df.dropna(subset=["harvest_date", "company", "crop", "amount_kg"])
if df.empty:
    st.error("有効なデータがありません。")
    st.stop()

st.subheader("プレビュー")
st.dataframe(df.head(20), use_container_width=True)


# =========================
# Insert
# =========================
ensure_table()

if st.button("この内容で DB に登録する", type="primary"):
    with st.spinner("DBに登録中..."):
        try:
            with engine.begin() as conn:
                df.to_sql("harvest_fact", conn, if_exists="append", index=False)
        except SQLAlchemyError as e:
            st.error("DB登録に失敗しました。")
            st.exception(e)
            st.stop()

    st.success(f"{len(df)} 行を登録しました。")
    st.info("Compass / SearchList を再読み込みしてください。")
    st.rerun()

