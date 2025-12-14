import os
import sys

import pandas as pd
import streamlit as st
from sqlalchemy.exc import OperationalError

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CURRENT_DIR)
ROOT_DIR = os.path.dirname(APP_DIR)

if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)


from core.auth import require_login
from core.db import get_engine, DB_PATH

require_login()

st.title("Search / List")
st.caption("収量データを条件で検索し、一覧表示・CSVダウンロードします")

engine = get_engine()

# DB読み込み
with st.spinner("収量データを読み込んでいます。"):
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(
                """
                select
                    date(harvest_date) as harvest_date,
                    company,
                    crop,
                    amount_kg
                from harvest_fact
                order by harvest_date
                """,
                conn,
            )

            df["harvest_date"] = pd.to_datetime(df["harvest_date"], errors="coerce")

    except OperationalError as e:
        st.error("SQLite データベースに接続できません。")
        st.code(str(DB_PATH), language="bash")
        st.exception(e)
        st.stop()

if df.empty:
    st.warning("収量データが登録されません。CSVアップロードからデータを登録してください。")
    st.stop()

df["harvest_date"] = pd.to_datetime(df["harvest_date"])

# フィルター　UI
st.subheader("検索条件")

min_date = df["harvest_date"].min().date()
max_date = df["harvest_date"].max().date()

date_start, date_end = st.date_input(
    "対象期間",
    (min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

all_companies = sorted(df["company"].unique().tolist())
company_filter = st.multiselect(
    "企業（未選択なら全件）",
    options=all_companies,
    default=[],
)

all_crops = sorted(df["crop"].unique().tolist())
crop_filter = st.multiselect(
    "作物（未選択なら全件）",
    options=all_crops,
    default=[],
)

# フィルター適用
filtered = df.copy()

filtered = filtered[
    (filtered["harvest_date"].dt.date >= date_start)
    & (filtered["harvest_date"].dt.date <= date_end)
]

if company_filter:
    filtered = filtered[filtered["company"].isin(company_filter)]

if crop_filter:
    filtered = filtered[filtered["crop"].isin(crop_filter)]

hit_count = len(filtered)

st.markdown("### 🔍　検索条件")
st.subheader(f"検索結果:{hit_count}行")

if hit_count == 0:
    st.warning("条件に一致するデータがありません。")
    st.stop()

# 一覧表示　＆　CDV　ダウンロード
st.dataframe(
    filtered.sort_values(["harvest_date", "company", "crop"]),
    width="stretch",)

st.success(f"{len(filtered)} 件のデータがヒットしました。")

# CSVダウンロード
csv_bytes = filtered.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    label="検索結果をCSVでダウンロード",
    data=csv_bytes,
    file_name="harvest_search_result.csv",
    mime="text/csv",
)

st.write("ここに収量データなどの検索・一覧画面を実装していきます。")

# ページネーション（25件ずつ）
page_size = 25
max_page = max(1, (len(filtered) + page_size - 1) // page_size)

if "page" not in st.session_state:
    st.session_state.page = 1

col_prev, col_mid, col_next = st.columns([1, 2, 1])

with col_prev:
    if st.button("←　前") and st.session_state.page > 1:
        st.session_state.page -= 1

with col_mid:
    st.write(f"ページ{st.session_state.page} / {max_page}")

with col_next:
    if st.button("次　→") and st.session_state.page < max_page:
        st.session_state.page += 1

start = (st.session_state.page - 1) * page_size
end = start + page_size

st.dataframe(
        filtered.sort_values(["harvest_date", "company", "crop"]).iloc[start:end],
        use_container_width=True,)
