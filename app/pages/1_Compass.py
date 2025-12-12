import os
import sys
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy.exc import OperationalError

# プロジェクトルートを sys.path に追加（どこから実行してもappを解決するため）
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CURRENT_DIR)
ROOT_DIR = os.path.dirname(APP_DIR)

if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.auth import require_login
from core.db import get_engine, DB_PATH

# 認証ガード
require_login()

st.title("Compass")
st.caption("収量の全体傾向をざっくりつかむダッシュボード")

engine = get_engine()

# DB から大量データを取得
with engine.connect() as conn:
    df = pd.read_sql_query(
        """
        select harvest_date, company, crop, amount_kg
        from harvest_fact
        """,
        conn,
        parse_dates=["harvest_date"],
    )

if df.empty:
    st.warning("まだ、harvest_factにデータが登録されていません。CSVアップロードからデータを登録してください。")
    st.stop()

# 日付を datetime 型に変換
df["harvest_date"] = pd.to_datetime(df["harvest_date"])

# フィルター　UI
st.subheader("フィルター")

# 日付範囲
min_date = df["harvest_date"].min().date()
max_date = df["harvest_date"].max().date()

st.markdown("### 期間フィルタ")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "開始日",
        value=max_date.replace(day=1),
        min_value=min_date,
        max_value=max_date,
    )
with col2:
    end_date = st.date_input(
        "終了日",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
    )

if start_date > end_date:
    st.error("開始日が終了日より後になっています。期間を見直してください。")
    st.stop()

mask = (df["harvest_date"].dt.date >= start_date) & (df["harvest_date"].dt.date <= end_date)
df_period = df[mask].copy()

if df_period.empty:
    st.warning("この期間にはデータがありません。別の期間を選んでください。")
    st.stop()

st.markdown("### 🚀 KPI 概要")

# KPI 指標（3つ）
total_kg = df_period["amount_kg"].sum()
days = df_period["harvest_date"].dt.date.nunique()
companies = df_period["company"].nunique()
crops = df_period["crop"].nunique()

avg_per_day = total_kg / days if days > 0 else 0.0

st.markdown("### KPI 概要")

k1, k2, k3 = st.columns(3)

with k1:
    st.metric("期間累計収量[kg]", f"{total_kg:.1f}")
with k2:
    st.metric("1日あたり平均収量[kg/日]", f"{avg_per_day:.1f}")
with k3:
    st.metric("企業数 / 作物数", f"{companies} 社　/ {crops} 品目")

# 企業別・作物別ランキング
st.markdown("### 企業別収量ランキング")

df_company = (
    df_period
    .groupby("company", as_index=False)["amount_kg"]
    .sum()
    .sort_values("amount_kg", ascending=False)
)

st.dataframe(df_company.head(5), width="stretch")

st.markdown("### 作物別収量ランキング")

df_company = (
    df_period
    .groupby("company", as_index=False)["amount_kg"]
    .sum()
    .sort_values("amount_kg", ascending=False)
)

st.dataframe(df_company.head(5), width="stretch")

st.markdown("### 作物別収量ランキング")

df_crop = (
    df_period
    .groupby("crop", as_index=False)["amount_kg"]
    .sum()
    .sort_values("amount_kg", ascending=False)
)

st.dataframe(df_crop.head(5), width="stretch")

st.markdown("----")

# 時系列グラフ
df_daily = (
    df_period
    .groupby("harvest_date", as_index=False)["amount_kg"]
    .sum()
)

chart = (
    alt.Chart(df_daily)
    .mark_line(point=True)
    .encode(
        x="harvest_date:T",
        y="amount_kg:Q",
        tooltip=["harvest_date:T", "amount_kg:Q"],
    )
    .properties(
        height=250,
        padding={"top": 30, "bottom": 10, "left": 10, "right": 10}
    )
)
st.altair_chart(chart, use_container_width=True)


bar = (
    alt.Chart(df_company_rank)
    .mark_bar(color="#4C78A8")
    .encode(
        x="amount_kg:Q",
        y=alt.Y("company:N", sort="-x"),
        tooltip=["company", "amount_kg"]
    )
    .properties(
        height=200,
        padding={"top": 20, "bottom":10}
    )
)

# 企業フィルタ
all_companies = sorted(df["company"].unique().tolist())
selected_companies = st.multiselect(
    "企業（複数選択可）",
    options=all_companies,
    default=all_companies,
)

# 作物フィルタ
all_crops = sorted(df["crop"].unique().tolist())
selected_crops = st.multiselect(
    "作物（複数選択可）",
    options=all_crops,
    default=all_crops,
)

# フィルター適用
filtered = df.copy()

# 日付
filtered = filtered[
    (filtered["harvest_date"].dt.date >= start_date)
    & (filtered["harvest_date"].dt.date <= end_date)
]

# 企業
if selected_companies:
    filtered = filtered[filtered["company"].isin(selected_companies)]

# 作物
if selected_crops:
    filtered = filtered[filtered["crop"].isin(selected_crops)]

if filtered.empty:
    st.warning("選択された条件に該当するデータがありません。フィルターを調整してください。")
    st.stop()

# メトリクス
st.markdown("---")

total_amount = float(filtered["amount_kg"].sum())
latest_date = filtered["harvest_date"].max()
latest_date_str = latest_date.strftime("%Y-%m-%d")
latest_total = float(filtered.loc[filtered["harvest_date"] == latest_date, "amount_kg"].sum())
num_companies = int(filtered["company"].nunique())

col1, col2, col3 = st.columns(3)
col1.metric("総収量（㎏）", f"{total_amount:.1f}")
col2.metric(f"最新日({latest_date_str})の収量（㎏）", f"{latest_total:.1f}")
col3.metric("企業数", f"{num_companies}")

st.markdown("----")

# グラフ

# 日別合計グラフ
daily = (
    filtered.groupby("harvest_date", as_index=False)["amount_kg"]
    .sum()
    .sort_values("harvest_date")
)
st.subheader("日別収量の推移")
st.line_chart(daily, x="harvest_date", y="amount_kg")

# 企業別合計グラフ
company = (
    filtered.groupby("company", as_index=False)["amount_kg"]
    .sum()
    .sort_values("amount_kg", ascending=False)
)
st.subheader("企業別収量（合計）")
st.bar_chart(company, x="company", y="amount_kg")

st.markdown("---")

# 生データ
st.subheader("生データ(harvest_fact)")
st.dataframe(
    filtered.sort_values(["harvest_date", "company", "crop"]),
    width="stretch",
)
