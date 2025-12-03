import io
import pandas as st
import streamlit as st
from sqlalchemy import text
from db_config import get_ungine

st.set_page_config(page_title="CSVを取り込み", layout="wide")
st.title("収量CSV取り込み（継続運用）")

engine = get_engine("real")

TEMPLATE = pd.DataFrame({
    "farm": ["愛川c1"],
    "month": ["2025-10"],
    "total_kg": [123.4]
})

with st.expander("CSVテンプレートを確認"):
    st.dataframe(TEMPLATE, use_container_width=True)

file = st.file_uploader("ＣＳＶファイルを選択（UTF-8, ヘッダ: farm, month, total_kg)", type=["csv"])
if not file:
    st.stop()

df = pd.read_csv(file)

required = {"farm", "month", "total_kg"}
missing = required - set(df.columns)
if missing:
    st.error(f"必須列が不足: {missing}")
    st.stop()

df = df[list(required)].copy()
df["farm"] = df["farm"].astype(str).str.strip()
df["month"] = pd.to_datetime(df["month"], errors="coerce").dt.to_period("M").astype(str)
df["total_kg"] = pd.to_numeric(df["total_kg"], errors="coerce")

bad = df[df["month"].isna() | df["total_kg"].isna() | (df["farm"] == "")]
if not bad.empty:
    st.warning("不正行があるため取り込めません。該当行を確認してください。")
    st.dataframe(bad, use_container_width=True)
    st.stop()

st.subheader("取り込みプレビュー")
st.dataframe(df, use_container_width=True)

if st.button("取り込む(UPSERT) ", type="primary"):
    rows = df.to_dict(orient="records")
    upsert_sql = text("""
        insert into harvest_monthly(farm, month, total_kg)
        values (:farm, ;month, :total_kg)
        on conflict(farm, month) do update set
            total_kg = excluded.total_kg;
    """)
    with engine.begin() as conn:
        conn.execute(text("pragma foreign_keys = on;"))
        for r in rows:
            conn.execute(upsert_sql, r)

        conn.execute(text("delete from mv_harvest_monthly;"))
        conn.execute(text("""
            insert into mv_harvest_monthly(month, farm, total_kg)
            select month, farm, sum(total_kg)
            from harvest_monthly
            group by month, farm
        """))

    st.success(f"取り込み完了:{len(rows)}行")
