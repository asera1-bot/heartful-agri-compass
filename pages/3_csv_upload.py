from __future__ import annotations

import io
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from app.core.auth import require_login
from app.core.db import get_engine, init_db
from app.common.constants import DB_PATH

st.set_page_config(page_title="CSV Upload", layout="wide")
require_login()
init_db()

if st.session_state.get("after_insert_message"):
    st.info(
        "CSVの登録が完了しました。\n\n"
        "🔄️登録内容を確認するには、左メニューから"
        "Compass または Search List ページを開きなおしてください。 \n"
        "(Streamlitの仕様上、他ページは自動更新されません。 )"
    )
    del st.session_state["after_insert_message"]

st.title("CSV Upload")
st.caption("収量データCSVをアップロードして harvest_fact に登録します。")
st.caption(f"DB_PATH={DB_PATH} exists={os.path.exists(DB_PATH)}")

# ---------- helpers ----------
ZEN_NUM = str.maketrans("０１２３４５６７８９．，", "0123456789.,")
EXCEL_EPOCH = datetime(1899, 12, 30)

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
    if "kg" in s_low:
        return x
    # g想定
    return x / 1000.0

def parse_harvest_date(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    # Excelシリアル
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

def read_csv_bytes(b: bytes) -> tuple[pd.DataFrame, str]:
    candidates = [
        ("utf-8-sig", dict(encoding="utf-8-sig", sep=",")),
        ("cp932", dict(encoding="cp932", sep=",")),
        ("cp932_auto", dict(encoding="cp932", sep=None, engine="python")),
    ]
    last = []
    for label, params in candidates:
        try:
            buf = io.BytesIO(b)
            return pd.read_csv(buf, **params), label
        except Exception as e:
            last.append(f"{label}: {e}")
    raise RuntimeError("CSV decode failed:\n" + "\n".join(last))

def ensure_table():
    ddl = """
    CREATE TABLE IF NOT EXISTS harvest_fact (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        harvest_date TEXT NOT NULL,
        company      TEXT NOT NULL,
        crop         TEXT NOT NULL,
        amount_kg    REAL NOT NULL
    );
    """
    eng = get_engine()
    with eng.begin() as conn:
        conn.exec_driver_sql(ddl)

def norm_col(x: str) -> str:
    return str(x).replace("\ufeff", "").replace("　", " ").strip().lower()

COL_MAP = {
    "収穫日": "harvest_date",
    "日付": "harvest_date",
    "harvest_date": "harvest_date",
    "date": "harvest_date",

    "企業名": "company",
    "会社名": "company",
    "企業": "company",
    "会社": "company",
    "company": "company",

    "作物名": "crop",
    "収穫野菜名": "crop",
    "品目": "crop",
    "crop": "crop",

    "収穫量（ｇ）": "amount_g",
    "収穫量(ｇ)": "amount_g",
    "収穫量": "amount_g",
    "量": "amount_g",
    "収量(㎏)": "amount_kg",
    "収量(kg)": "amount_kg",
    "amount_g": "amount_g",
    "amount_kg": "amount_kg",
}

# ---------- UI ----------
uploaded = st.file_uploader("収量CSVを選択", type=["csv"])
if uploaded is None:
    st.info("CSVを選択してください。")
    st.stop()

raw_df, mode = read_csv_bytes(uploaded.getvalue())
st.success(f"CSV読み込み成功 (mode={mode})")
st.write("検出列:", list(raw_df.columns))

# ---------- normalize columns ----------
rename = {}
for c in raw_df.columns:
    key = norm_col(c)
    mapped = COL_MAP.get(key) or COL_MAP.get(str(c).replace("\ufeff", "").replace("　", " ").strip())
    if mapped:
        rename[c] = mapped

df = raw_df.rename(columns=rename)

required = {"harvest_date", "company", "crop"}
if not required.issubset(df.columns):
    st.error(f"必須列が不足しています: {required - set(df.columns)}")
    st.write("正規化後の列:", [norm_col(x) for x in raw_df.columns])
    st.stop()

# amount_kg 作成
if "amount_kg" in df.columns:
    df["amount_kg"] = df["amount_kg"].apply(parse_amount_to_kg)
elif "amount_g" in df.columns:
    df["amount_kg"] = df["amount_g"].apply(parse_amount_to_kg)
else:
    st.error("収量列が見つかりません（amount_g/amount_kg が必要）")
    st.stop()

df["harvest_date"] = df["harvest_date"].apply(parse_harvest_date)
df["company"] = df["company"].astype(str).str.strip()
df["crop"] = df["crop"].astype(str).str.strip()

df = df.dropna(subset=["harvest_date", "company", "crop", "amount_kg"])
df = df[(df["company"] != "") & (df["crop"] != "")]
df = df[["harvest_date", "company", "crop", "amount_kg"]].copy()

st.markdown("### プレビュー（登録対象）")
st.dataframe(df.head(30), use_container_width=True)

if df.empty:
    st.warning("有効データがありません。CSV内容を確認してください。")
    st.stop()

result_box = st.container()

if st.button("この内容でDBに登録", type="primary"):
    ensure_table()
    eng = get_engine()

    rows = df.to_dict(orient="records")

    sql = """
    INSERT OR IGNORE INTO harvest_fact
    (harvest_date, company, crop, amount_kg)
    VALUES (:harvest_date, :company, :crop, :amount_kg)
    """

    try:
        with eng.begin() as conn:
            # 登録前件数
            before_n = conn.execute(text("SELECT COUNT(*) FROM harvest_fact")).scalar_one()

            # 一括登録（重複は無視）
            conn.execute(text(sql), rows)

            # 登録後件数
            after_n = conn.execute(text("SELECT COUNT(*) FROM harvest_fact")).scalar_one()

        inserted = after_n - before_n
        skipped = len(rows) - inserted

        with result_box:
            st.success(f"登録処理が完了しました。追加: {inserted}件 / スキップ: {skipped}件（重複など）")

            if skipped > 0:
                st.info("スキップ理由：同一キー（harvest_date, company, crop, amount_kg）が既にDBに存在するためです。")

            st.info(
                "🔄 登録内容を確認するには、左メニューから **Compass** または **Search / List** ページを開き直してください。\n"
                "（Streamlitの仕様上、他ページの表示は自動更新されません）"
            )

    except Exception as e:
        with result_box:
            st.error("DB登録に失敗しました。")
            st.exception(e)

