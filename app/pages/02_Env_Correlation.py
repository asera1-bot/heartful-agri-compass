import streamlit as st
import pandas as pd
import statsmodels.api as sm
import plotly.express as px

from db_config import get_engine

st.set_page_config(page_title="環境相関", layout="wide")
st.title("環境データ × 収量")

engine = get_engine()

# =========================
# ユーティリティ関数
# =========================
@st.cache_data(ttl=60)
def months():
    q = "SELECT DISTINCT month FROM harvest_monthly ORDER BY month"
    return pd.read_sql(q, engine)["month"].tolist()

@st.cache_data(ttl=60)
def env_rows_in_month(month: str):
    q = """
        SELECT *
        FROM env_rows
        WHERE substr(ts, 1, 7) = :m
    """
    return pd.read_sql(q, engine, params={"m": month})

@st.cache_data(ttl=60)
def harvest_in_month(month: str):
    q = """
        SELECT farm, total_kg
        FROM harvest_monthly
        WHERE month = :m
        ORDER BY total_kg DESC
    """
    return pd.read_sql(q, engine, params={"m": month})

# =========================
# ① 月別の収量ランキング & 環境時系列
# =========================
m = months()
if not m:
    st.info("harvest_monthly が空です。")
    st.stop()

sel_month = st.selectbox("月を選択 (YYYY-MM)", m, index=len(m)-1)
env = env_rows_in_month(sel_month)
har = harvest_in_month(sel_month)

left, right = st.columns(2)
with left:
    st.subheader(f"収量ランキング ({sel_month})")
    st.dataframe(har, use_container_width=True, hide_index=True)

with right:
    st.subheader(f"環境データ ({sel_month})")
    if env.empty:
        st.info("この月の env_rows はありません。")
    else:
        # 任意の列を選んで時系列表示 (c2..c10 あたりを候補に)
        cols = [c for c in env.columns if c.startswith("c")]

        options = cols[:10]
        default = cols[:2] if len(cols) >= 2 else cols

        pick = st.multiselect(
            "プロットする列（複数可）",
            options,
            default=default,
            key="env_cols",
        )

        if pick:
            ts = env[["ts"] + pick].copy()
            ts["ts"] = pd.to_datetime(ts["ts"], errors="coerce")
            ts = ts.dropna(subset=["ts"]).sort_values("ts")
            if not ts.empty:
                st.line_chart(ts.set_index("ts"))
            else:
                st.info("この月の時系列データがありません。")
        else:
            st.info("プロットする列を選んでください。")

# =========================
# ② 全期間の環境 × 収量相関
# =========================
st.markdown("---")
st.title("環境と収量の相関分析（全期間）")

q = """
    SELECT month, farm, total_kg, avg_temp, avg_humid
    FROM v_harvest_env
    WHERE total_kg IS NOT NULL
"""
df = pd.read_sql(q, engine)

if df.empty:
    st.info("v_harvest_env にデータがありません。")
    st.stop()

months_all = sorted(df["month"].unique())
farms_all = sorted(df["farm"].unique())

sel_months = st.multiselect("月を選択", months_all, default=months_all[-3:])
sel_farms = st.multiselect("ファームを選択", farms_all, default=farms_all[:5])

filtered = df[df["month"].isin(sel_months) & df["farm"].isin(sel_farms)]

if not filtered.empty:
    # 散布図（温度）
    fig = px.scatter(
        filtered,
        x="avg_temp",
        y="total_kg",
        color="farm",
        trendline="ols",
        labels={"avg_temp": "平均温度（℃）", "total_kg": "収量（kg）"},
        title="平均温度と収量の相関",
    )
    st.plotly_chart(fig, use_container_width=True)

    # 散布図（湿度）
    fig2 = px.scatter(
        filtered,
        x="avg_humid",
        y="total_kg",
        color="farm",
        trendline="ols",
        labels={"avg_humid": "平均湿度（％）", "total_kg": "収量（kg）"},
        title="平均湿度と収量の相関",
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("統計サマリ")

    # 欠損を除いてから相関を計算
    sub_temp = filtered[["avg_temp", "total_kg"]].dropna()
    sub_humid = filtered[["avg_humid", "total_kg"]].dropna()

    cols1, cols2 = st.columns(2)

    # ---------- 温度側 ----------
    with cols1:
        if len(sub_temp) >= 3:
            corr_temp = sub_temp["avg_temp"].corr(sub_temp["total_kg"])
            if pd.isna(corr_temp):
                corr_temp = 0.0
            st.markdown(f"**温度×収量の相関係数 r**: `{corr_temp:.3f}`")

            # 単回帰 (total_kg ~ avg_temp)
            X = sm.add_constant(sub_temp[["avg_temp"]], has_constant="add")
            y = sub_temp["total_kg"]
            model_temp = sm.OLS(y, X).fit()

            params = model_temp.params
            intercept = params.get("const", 0.0)
            slope = params.get("avg_temp", 0.0)
            r2 = model_temp.rsquared or 0.0

            st.markdown(
                f"- 回帰式: `収量 = {intercept:.1f} + {slope:.2f} × 温度`"
            )
            st.markdown(f"- 決定係数 R²: `{r2:.3f}`")
        else:
            st.info("温度データが少なすぎて相関を計算できません。")

    # ---------- 湿度側 ----------
    with cols2:
        if len(sub_humid) >= 3:
            corr_humid = sub_humid["avg_humid"].corr(sub_humid["total_kg"])
            if pd.isna(corr_humid):
                corr_humid = 0.0
            st.markdown(f"**湿度×収量の相関係数 r**: `{corr_humid:.3f}`")

            Xh = sm.add_constant(sub_humid[["avg_humid"]], has_constant="add")
            yh = sub_humid["total_kg"]
            model_humid = sm.OLS(yh, Xh).fit()

            params_h = model_humid.params
            intercept_h = params_h.get("const", 0.0)
            slope_h = params_h.get("avg_humid", 0.0)
            r2_h = model_humid.rsquared or 0.0

            st.markdown(
                f"- 回帰式: `収量 = {intercept_h:.1f} + {slope_h:.2f} × 湿度`"
            )
            st.markdown(f"- 決定係数 R²: `{r2_h:.3f}`")
        else:
            st.info("湿度データが少なすぎて相関を計算できません。")

    st.subheader("対象データ")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
else:
    st.info("該当データがありません。")
import numpy as np
import statsmodels.api as sm
import plotly.express as px
import streamlit as st
import pandas as pd
from db_config import get_engine

st.set_page_config(page_title="環境相関", layout="wide")
st.title("環境データ　×　収量")

engine = get_engine()

@st.cache_data(ttl=60)
def months():
    return pd.read_sql("select distinct month from harvest_monthly order by month", engine)["month"].tolist()

@st.cache_data(ttl=60)
def env_rows_in_month(month: str):
    q = """
    select * from env_rows
    where substr(ts,1,7)=:m
    """
    return pd.read_sql(q, engine, params={"m": month})

@st.cache_data(ttl=60)
def harvest_in_month(month: str):
    q = """
    select farm, total_kg
    from harvest_monthly
    where month=:m
    order by total_kg desc
    """
    return pd.read_sql(q, engine, params={"m": month})

m = months()
if not m:
    st.info("harvest_monthly が空です。")
    st.stop()

sel_month = st.selectbox("月を選択(YYYY-MM)", m, index=len(m)-1)
env = env_rows_in_month(sel_month)
har = harvest_in_month(sel_month)

left, right = st.columns(2)
with left:
    st.subheader(f"収量ランキング({sel_month})")
    st.dataframe(har, use_container_width=True, hide_index=True)

with right:
    st.subheader(f"環境データ({sel_month})")

