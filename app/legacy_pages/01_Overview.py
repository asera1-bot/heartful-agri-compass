import streamlit as st
import pandas as pd
from sqlalchemy import text
from db_config import get_engine

st.set_page_config(page_title="収量サマリ", layout="wide")
st.title("収量サマリ")

engine = get_engine()

@st.cache_data(ttl=60)
def load_harvest():
    q = "select month, farm, total_kg from harvest_monthly order by month, farm"
    return pd.read_sql(q, engine)

df = load_harvest()

left, right = st.columns([1,2])
with left:
    months = sorted(df["month"].unique()) if not df.empty else []
    farms = sorted(df["farm"].unique()) if not df.empty else []
    sel_months = st.multiselect("月を選択", months, default=months[-3:] if len(months)>=3 else months)
    sel_farms = st.multiselect("ファームを選択", farms)

f = df.copy()
if sel_months: f = f[f["month"].isin(sel_months)]
if sel_farms: f= f[f["farm"].isin(sel_farms)]

st.dataframe(f, use_container_width=True, hide_index=True)

if not f.empty:
    st.bar_chart(f, x="farm", y="total_kg", color="month")
