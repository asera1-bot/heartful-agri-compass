# pages/1_Compass.py
from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import require_login
from app.common.constants import DB_PATH
from app.core.db import get_engine, init_db


# =========================
# Page config (MUST be early)
# =========================
st.set_page_config(page_title="Compass", layout="wide")
st.title("Compass")
st.caption("収量の全体傾向をざっくりつかむダッシュボード")

# ログイン必須（UIは出しつつ、未ログインならここで止める）
require_login()

# DB初期化（CREATE TABLE IF NOT EXISTS までやる想定）
init_db()


# =========================
# Helpers
# =========================
def get_db_mtime() -> float:
    return DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0


@st.cache_data(show_spinner=False)
def load_harvest_df(db_mtime: float) -> pd.DataFrame:
    """DB更新時刻(db_mtime)をキーにキャッシュ無効化する"""
    engine = get_engine()
    sql = """
    SELECT
        harvest_date,
        company,
        crop,
        amount_kg
    FROM harvest_fact
    ORDER BY harvest_date, company, crop
    """
    df = pd.read_sql_query(sql, engine)

    # normalize
    df["harvest_date"] = pd.to_datetime(df["harvest_date"], errors="coerce")
    df["amount_kg"] = pd.to_numeric(df["amount_kg"], errors="coerce")
    df["company"] = df["company"].astype(str).str.strip()
    df["crop"] = df["crop"].astype(str).str.strip()

    df = df.dropna(subset=["harvest_date", "amount_kg", "company", "crop"])
    df = df[(df["company"] != "") & (df["crop"] != "")]
    return df


# =========================
# Load
# =========================
mtime = get_db_mtime()

try:
    with st.spinner("収量データを読み込んでいます..."):
        df = load_harvest_df(mtime)
except Exception as e:
    # テーブル未作成/DBパス不整合/SQLエラーなどはここに来る
    st.info("まず CSV Upload でデータを登録してください。")
    st.caption(f"DB_PATH={DB_PATH} exists={DB_PATH.exists()}")
    st.exception(e)
    st.stop()

if df.empty:
    st.info("harvest_fact にデータがありません。CSV Upload で登録してください。")
    st.stop()


# =========================
# Derived columns
# =========================
df["harvest_day"] = df["harvest_date"].dt.date
df_min = df["harvest_day"].min()
df_max = df["harvest_day"].max()
st.caption(f"DBデータ範囲: {df_min} ~ {df_max}")


# =========================
# Period Filter
# =========================
st.subheader("期間フィルタ")

DEFAULT_START = date(2024, 1, 1)
default_start = max(DEFAULT_START, df_min)
default_end = df_max

date_start, date_end = st.date_input(
    "対象期間",
    value=(default_start, default_end),
    min_value=df_min,
    max_value=df_max,
)

if date_start > date_end:
    st.error("開始日が終了日より後になっています。")
    st.stop()

df_period = df[(df["harvest_day"] >= date_start) & (df["harvest_day"] <= date_end)].copy()
if df_period.empty:
    st.info("この期間にはデータがありません。別の期間を選んでください。")
    st.stop()


# =========================
# Company/Crop Filter
# =========================
st.subheader("企業・作物フィルタ")

all_companies = sorted(df_period["company"].unique().tolist())
all_crops = sorted(df_period["crop"].unique().tolist())

c1, c2 = st.columns(2)
with c1:
    selected_companies = st.multiselect("企業（未選択＝全件）", options=all_companies, default=[])
with c2:
    selected_crops = st.multiselect("作物（未選択＝全件）", options=all_crops, default=[])

filtered = df_period
if selected_companies:
    filtered = filtered[filtered["company"].isin(selected_companies)]
if selected_crops:
    filtered = filtered[filtered["crop"].isin(selected_crops)]

if filtered.empty:
    st.warning("選択された条件に該当するデータがありません。フィルターを調整してください。")
    st.stop()


# =========================
# KPI
# =========================
st.subheader("🚀 KPI概要")

total_kg = float(filtered["amount_kg"].sum())
days = int(filtered["harvest_day"].nunique())
companies = int(filtered["company"].nunique())
crops = int(filtered["crop"].nunique())
avg_per_day = total_kg / days if days else 0.0

k1, k2, k3 = st.columns(3)
k1.metric("期間累計収量 [kg]", f"{total_kg:.1f}")
k2.metric("1日あたり平均収量 [kg/日]", f"{avg_per_day:.1f}")
k3.metric("企業数 / 作物数", f"{companies} 社 / {crops} 品目")


# =========================
# Rankings
# =========================
st.subheader("企業別収量ランキング")
df_company = (
    filtered.groupby("company", as_index=False)["amount_kg"]
    .sum()
    .sort_values("amount_kg", ascending=False)
)
top_n_company = st.slider("表示する企業数（TopN）", 5, 50, 10, 5)
st.dataframe(df_company.head(top_n_company), use_container_width=True)

st.subheader("作物別収量ランキング")
df_crop = (
    filtered.groupby("crop", as_index=False)["amount_kg"]
    .sum()
    .sort_values("amount_kg", ascending=False)
)
top_n_crop = st.slider("表示する作物数（TopN）", 5, 50, 10, 5)
st.dataframe(df_crop.head(top_n_crop), use_container_width=True)


# =========================
# Charts
# =========================
st.subheader("日別収量の推移")
df_daily = (
    filtered.groupby("harvest_day", as_index=False)["amount_kg"]
    .sum()
    .sort_values("harvest_day")
)
st.line_chart(df_daily, x="harvest_day", y="amount_kg")

st.subheader("企業別収量（合計）")
st.bar_chart(df_company.head(top_n_company), x="company", y="amount_kg")


# =========================
# Raw table (paged)
# =========================
st.subheader("生データ（harvest_fact）")
show_cols = ["harvest_day", "company", "crop", "amount_kg"]

page_size = st.selectbox("生データの表示件数", [25, 50, 100, 200], index=0)
max_page = max(1, (len(filtered) + page_size - 1) // page_size)

if "compass_page" not in st.session_state:
    st.session_state["compass_page"] = 1

p1, p2, p3 = st.columns([1, 2, 1])
with p1:
    if st.button("← 前", use_container_width=True) and st.session_state["compass_page"] > 1:
        st.session_state["compass_page"] -= 1
with p2:
    st.write(f"ページ {st.session_state['compass_page']} / {max_page}")
with p3:
    if st.button("次 →", use_container_width=True) and st.session_state["compass_page"] < max_page:
        st.session_state["compass_page"] += 1

start = (st.session_state["compass_page"] - 1) * page_size
end = start + page_size

view = filtered[show_cols].sort_values(["harvest_day", "company", "crop"]).iloc[start:end]
st.dataframe(view, use_container_width=True)

