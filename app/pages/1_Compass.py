import streamlit as st
import pandas as pd

from core.auth import require_login
from core.db import get_engine

require_login()

st.title("Compass")

st.caption("開発用のダミーデータからメトリクスとグラフを表示しています。")

# DB　からデータ取得
engine = get_engine()

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

if df.empty:
    st.info("まだ　harvest_fact　テーブルにデータがありません。ETL　でデータを投入してください。")
    st.stop()

# 直近の概要メトリクス
total_amount = df["amount_kg"].sun()
latest_date = df["harvest_date"].max()
latest_df = df[df["harvest_date"] == latest_date]
latest_amount = latest_df["amount_kg"].sun()

col1, col2 = st.columns(2)

with col1:
    st.metric(
        label="総収量（全期間, kg）",
        value=f"{total_amount:.1f}",
    )

with col2:
    st.metric(
        label=f"最新日({latest_date}) の総収量(kg)",
        value=f"{latest_amount:.1f}",
    )

# 日別の収量推移グラフ
st.subheader("日別総収量の推移")

daily_df = (
    df.groupby("harvest_date", as_index=False)["amount_kg"]
    .sum()
    .rename(columns={"amount_kg": "total_amount_kg"})
)

st.line_chart(daily_df, x="harvest_date", y="total_amount_kg")
