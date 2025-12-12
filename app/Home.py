import streamlit as st
import pandas as pd
from sqlalchemy import text
from db_config import get_engine

st.set_page_config(page_title="Heartful Analytics", layout="wide")
st.title("はーとふる農園ダッシュボード(Stage)")

engine = get_engine()

@st.cache_data(ttl=60)
def load_counts():
    q = """
    select 'raw_csv' as tbl, count(*) as rows from raw_csv
    union all select 'env_header', count(*) from env_header
    union all select 'env_rows', count(*) from env_rows
    union all select 'staging', count(*) from staging_monthly
    union all select 'harvest', count(*) from harvest_monthly
    """
    return pd.read_sql(q, engine)

@st.cache_data(ttl=60)
def load_harvest_summary():
    q = """
    select month, sum(total_kg) as total_kg
    from harvest_monthly
    group by month
    order by month
    """
    return pd.read_sql(q, engine)

col1, col2 = st.columns([1,2], gap="large")

with col1:
    st.subheader("テーブル件数")
    st.dataframe(load_counts(), width="stretch", hide_index=True)

with col2:
    st.subheader("月次合計（全ファーム）")
    df = load_harvest_summary()
    if not df.empty:
        st.bar_chart(df, x="month", y="total_kg")
    else:
        st.info("harvest_monhtly が空です。")

