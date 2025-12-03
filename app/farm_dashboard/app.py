import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px
import yaml

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
CFG = yaml.safe_load((ROOT / "config" / "app.yaml").read_text(encoding="utf-8"))
DB = (ROOT / CFG["db_path"]).resolve()

st.set_page_config(page_title=CFG.get("app_title", "Farm Dashboard"), layout="wide")

def list_tables(db_path: Path) -> pd.DataFrame:
    try:
        with sqlite3.connect(str(db_path)) as conn:
            return pd.read_sql(
                    "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY type, name;",
                    conn
            )
        except Exception as e:
            return pd.DataFrame({"name":[f"ERROR: {e}"], "type":[""]})

@st.cache_data(ttl=30)
def load_df(table: str) -> pd.DataFrame:
    q_mv   = "SELECT month, farm, total_kg FROM mv_farm_totals ORDER BY month, farm"
    q_view = "SELECT month, farm, total_kg FROM v_farm_month_totals ORDER BY month, farm"
    query  = q_mv if source == "mv" else q_view
    with sqlite3.connect(str(DB)) as conn:
        return pd.read_sql(query, conn)

def main():
    st.title(CFG.get("app_title", "Farm Dashboard"))

# デバック情報（折り畳み）
    with st.expander("Debug（環境確認）)", expanded=False):
        st.write("DB path:", str(DB))
        st.write("Exists:, DB.exists())
        st.dataftame(list_tables(DB), use_conteiner_width=True, hide_index=True)

        source = st.radio(
            "データソース", ["mv", "view"],
            index=0 if CFG.get("dafault_source","mv") else 1,
            horizontal=True
        )

        try:
            df = load_df(source)
        except Exception as e:
            st.error(f"データ読み込みでエラー:{e}")
            st.stop()
        c1, c2 = st.columns([2,3])
        with c2:
            if df.empty:
                st.info("データがありません。")
            else:
            fig = px.bar(df, x="month", y="total_kg", color="farm", barmode="group", text="total_kg",
                         title=f"月別　ｘ　圃場合計（{source.upprr()})")
            st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__"
    main()
