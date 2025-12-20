import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import require_login
from app.core.db import get_engine, DB_PATH

require_login()

st.title("Search / List")
st.caption("収量データを条件で検索し、一覧表示・CSVダウンロードします。")

# --------------------
# DB Load
# --------------------
@st.cache_data(ttl=60)
def load_harvest_df() -> pd.DataFrame:
    # ✅ cache関数内でengineを作る（Streamlitの実行/キャッシュ境界で安全）
    engine = get_engine()

    sql = text("""
        SELECT
            harvest_date,
            company,
            crop,
            amount_kg
        FROM harvest_fact
        ORDER BY harvest_date, company, crop
    """)

    with engine.connect() as conn:
        df = pd.read_sql_query(sql, conn)

    # harvest_date は TEXT(YYYY-MM-DD) 想定。念のため変換
    df["harvest_date"] = pd.to_datetime(df["harvest_date"], errors="coerce")
    df = df.dropna(subset=["harvest_date"])

    df = df[df["harvest_date"] >= pd.Timestamp("2024-01-01")]
    return df


with st.spinner("収量データを読み込んでいます..."):
    try:
        df = load_harvest_df()
    except SQLAlchemyError as e:
        st.error("DB読み込みに失敗しました。")
        st.code(str(DB_PATH), language="bash")
        st.exception(e)
        st.stop()

if df.empty:
    st.warning("収量データがありません。CSVアップロード/ETLでデータを登録してください。")
    st.stop()

from datetime import date

# --------------------
# Filter UI
# --------------------
st.subheader("検索条件")

df["harvest_date"] = pd.to_datetime(df["harvest_date"], errors="coerce")
df["harvest_date"] = df["harvest_date"].dt.date

df_min = df["harvest_date"].min()
df_max = df["harvest_date"].max()

st.caption(f"DBデータ範囲: {df_min} ~ {df_max}")

DEFAULT_START = date(2024, 1, 1)
DEFAULT_END = df_max

default_start = max(DEFAULT_START, df_min)
default_end = min(DEFAULT_END, df_max)

date_start, date_end = st.date_input(
    "対象期間",
    value=(default_start, default_end),
    min_value=df_min,
    max_value=df_max,
)

if date_start > date_end:
    st.error("開始日が終了日より後になっています。")
    st.stop()

# --------------------
# Company / Crop filters
# --------------------
all_companies = sorted(df["company"].dropna().unique().tolist())
company_filter = st.multiselect(
    "企業（未選択なら全件）",
    options=all_companies,
    default=[]
)

all_crops = sorted(df["crop"].dropna().unique().tolist())
crop_filter = st.multiselect(
    "作物（未選択なら全件)",
    options=all_crops,
    default=[]
)
# --------------------
# Apply filters
# --------------------
filtered = df[
    (df["harvest_date"] >= date_start)
    & (df["harvest_date"] <= date_end)
].copy()

if company_filter:
    filtered = filtered[filtered["company"].isin(company_filter)]

if crop_filter:
    filtered = filtered[filtered["crop"].isin(crop_filter)]

hit_count = len(filtered)

st.markdown("### 検索結果")
st.subheader(f"検索結果: {hit_count} 行")

if hit_count == 0:
    st.warning("条件に一致するデータがありません。")
    st.stop()

# --------------------
# Pagination (only ONE table)
# --------------------
page_size = st.selectbox("表示件数", [25, 50, 100, 200], index=0)

# ✅ page 初期化（KeyError防止）
if "page" not in st.session_state:
    st.session_state["page"] = 1

# フィルタ条件が変わったらページを1に戻す（事故防止）
sig = (
    f"{date_start}|{date_end}|"
    + "|".join(company_filter)
    + "|"
    + "|".join(crop_filter)
    + f"|{page_size}|{hit_count}"
)
if st.session_state.get("_sig") != sig:
    st.session_state["_sig"] = sig
    st.session_state["page"] = 1

max_page = max(1, (hit_count + page_size - 1) // page_size)

col_prev, col_mid, col_next = st.columns([1, 2, 1])
with col_prev:
    if st.button("← 前", use_container_width=True) and st.session_state["page"] > 1:
        st.session_state["page"] -= 1
with col_mid:
    st.write(f"ページ {st.session_state['page']} / {max_page}")
with col_next:
    if st.button("次 →", use_container_width=True) and st.session_state["page"] < max_page:
        st.session_state["page"] += 1

start = (st.session_state["page"] - 1) * page_size
end = start + page_size

view = filtered.sort_values(["harvest_date", "company", "crop"]).iloc[start:end]

st.dataframe(view, use_container_width=True)
st.success(f"{hit_count} 件のデータがヒットしました。")

# --------------------
# CSV download
# --------------------
csv_bytes = (
    filtered.sort_values(["harvest_date", "company", "crop"])
    .to_csv(index=False)
    .encode("utf-8-sig")
)
st.download_button(
    label="検索結果をCSVでダウンロード",
    data=csv_bytes,
    file_name="harvest_search_result.csv",
    mime="text/csv",
)

