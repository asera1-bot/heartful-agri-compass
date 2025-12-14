import os
import sys

import pandas as pd
import streamlit as st
from sqlalchemy.exc import OperationalError

# プロジェクトルートをsys.pathに追加
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

# DBからデータ取得
try:
    with engine.connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT harvest_date, company, crop, amount_kg
            FROM harvest_fact
            """,
            conn,
            parse_dates=["harvest_date"]
        )
except OperationalError as e:
    st.error(f"DB読み込みに失敗しました: {e}")
    st.stop()

if df.empty:
    st.warning("harvest_factにデータが登録されていません。CSVアップロードからデータを登録してください。")
    st.stop()

# 日付をdatetimeに変換
df["harvest_date"] = pd.to_datetime(df["harvest_date"], errors="coerce")
df = df.dropna(subset=["harvest_date"])
df["amount_kg"] = pd.to_numeric(df["amount_kg"], errors="coerce")
df = df.dropna(subset=["amount_kg", "amount_kg", "company", "crop"]).copy()
df = df[df["harvest_date"] >= pd.Timestamp("2020-01-01")]

# 表示・フィルタ用（日付だけ）
df["harvest_day"] = df["harvest_date"].dt.date

# フィルターUI
st.subheader("期間フィルタ")

from datetime import date, timedelta

min_date = df["harvest_date"].min().date()
max_date = df["harvest_date"].max().date()

st.caption(f"DBデータ範囲: {min_date} ~ {max_date}")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "開始日",
        value=min_date,
    )

with col2:
    end_date = st.date_input(
        "終了日",
        value=max_date,
    )

if start_date > end_date:
    st.error("開始日が終了日より後になっています。期間を見直してください。")
    st.stop()

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

if start_date > end_date:
    st.error("開始日が終了日よりも後です。")
    st.stop()

mask = (df["harvest_date"].dt.date >= start_date) & (df["harvest_date"].dt.date <= end_date)
df_period = df[mask].copy()

if df_period.empty:
    msg = f"選択期間にデータなし: start={start_date}, end={end_date} (db_range={min_date}~{max_date})"
    st.info("この期間にはデータがありません。CSV登録状況を確認してください。")
    logger.info(msg)
    print("[INFO]", msg)
    st.stop()

# まず期間で絞る（ここが土台）
df_period = df[(df["harvest_day"] >= start_date) & (df["harvest_day"] <= end_date)].copy()

if df_period.empty:
    st.warning("この期間にはデータがありません。別の期間を選んでください。")
    st.stop()

# 企業フィルタ/作物の選択肢は「期間内」に限定（ＵＩが軽くなる）
all_companies = sorted(df["company"].unique().tolist())
all_crops = sorted(df["crop"].unique().tolist())

st.subheader("企業・作物フィルタ")
cc1, cc2 = st.columns(2)
with cc1:
    selected_companies = st.multiselect(
        "企業（未選択＝全件）",
        options=all_companies,
        default=[],
    )
with cc2:
    selected_crops = st.multiselect(
        "作物（未選択＝全件）",
        options=all_crops,
        default=[],
    )

# フィルター適用
filtered = df_period.copy()

if selected_companies:
    filtered = filtered[filtered["company"].isin(selected_companies)]
if selected_crops:
    filtered = filtered[filtered["crop"].isin(selected_crops)]

if filtered.empty:
    st.warning("選択された条件に該当するデータがありません。フィルターを調整してください。")
    st.stop()

if filtered.empty:
    msg = f"フィルター条件でデータなし: start={start_date}, end={end_date}, companies={selected_companies}, crops={selected_crops}"
    st.warning("選択された条件に該当するデータがありません。フィルターを調整してください。")
    logger.info(msg)
    print("[INFO]", msg)
    st.stop()

# KPI指標（3つ）
st.subheader("🚀KPI概要")

total_kg = float(filtered["amount_kg"].sum())
days = int(filtered["harvest_day"].nunique())
companies = int(filtered["company"].nunique())
crops = int(filtered["crop"].nunique())
avg_per_day = total_kg / days if days > 0 else 0.0

k1, k2, k3 = st.columns(3)
k1.metric("期間累計収量[kg]", f"{total_kg:.1f}")
k2.metric("１日あたり平均収量[kg/日]", f"{avg_per_day:.1f}")
k3.metric("企業数 / 作物数", f"{companies} 社 / {crops} 品目")

# ランキング（Top5）
st.subheader("企業別収量ランキング(Top5)")
df_company = (
    filtered.groupby("company", as_index=False)["amount_kg"]
    .sum()
    .sort_values("amount_kg", ascending=False)
)
st.dataframe(df_company.head(5), width="stretch")

st.subheader("作物別収量ランキング(Top5)")
df_crop = (
    filtered.groupby("crop", as_index=False)["amount_kg"]
    .sum()
    .sort_values("amount_kg", ascending=False)
)
st.dataframe(df_crop.head(5), width="stretch")

# グラフ
st.subheader("日別収量の推移")
df_daily = (
    filtered.groupby("harvest_day", as_index=False)["amount_kg"]
    .sum()
    .sort_values("harvest_day")
)
st.line_chart(df_daily, x="harvest_day", y="amount_kg")

st.subheader("企業別収量（合計）")
top_n = st.slider("表示する企業数（TopN）", 5, 50, 10, 5)
df_company_top = df_company.head(top_n)
st.bar_chart(df_company_top, x="company", y="amount_kg")

# 生データ
st.subheader("生データ(harvest_fact")
show_cols = ["harvest_day", "company", "crop", "amount_kg"]
st.dataframe(
    filtered[show_cols].sort_values(["harvest_day", "company", "crop"]),
    width="stretch")
