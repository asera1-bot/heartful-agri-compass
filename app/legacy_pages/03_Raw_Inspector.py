from pathlib import Path
import sys

import streamlit as st
import pandas as pd
import statsmodels.api as sm
import altair as alt

# プロジェクトルート（heartful-analytics）を import パスに追加
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from db_config import get_engine


@st.cache_data
def load_summary() -> pd.DataFrame:
    """
    v_harvest_env からダッシュボード用のサマリを取得する。
    """
    engine = get_engine("real")
    q = """
        SELECT
            farm,
            month,
            mean_temp,
            mean_humid,
            mean_vpd_kpa,
            mean_sand_temp,
            mean_water_content AS mean_water,
            mean_irradiance,
            mean_kg
        FROM v_harvest_env
        WHERE mean_temp    IS NOT NULL
          AND mean_humid   IS NOT NULL
          AND mean_vpd_kpa IS NOT NULL
          AND mean_kg      IS NOT NULL
        ORDER BY farm, month;
    """
    return pd.read_sql(q, engine)


# ----------------- 画面レイアウト -----------------
st.set_page_config(page_title="全期間　相関分析", layout="wide")
st.title("環境データ × 収量（全期間サマリ）")

df = load_summary()
st.write("▼ df のカラム一覧（内部）", list(df.columns))

if df.empty:
    st.info("v_harvest_env に有効なデータがありません。")
    st.stop()

# 表示用だけ日本語化
df_display = df.rename(
    columns={
        "farm": "農場",
        "month": "月",
        "mean_temp": "平均温度",
        "mean_humid": "平均湿度",
        "mean_vpd_kpa": "平均VPD(kPa)",
        "mean_sand_temp": "平均砂温度",
        "mean_water": "平均水分量",
        "mean_irradiance": "平均放射(W/m2)",
        "mean_kg": "平均収量(kg)",
    }
)

st.subheader("平均値サマリ（農場 × 月）")
st.dataframe(df_display, width="stretch", hide_index=True)

# ----------------- 相関 -----------------
corr_temp = df["mean_temp"].corr(df["mean_kg"])
corr_humid = df["mean_humid"].corr(df["mean_kg"])

st.markdown("### 統計サマリ（相関）")
st.markdown(f"- **温度×収量の相関係数 r** : `{corr_temp:.3f}`")
st.markdown(f"- **湿度×収量の相関係数 r** : `{corr_humid:.3f}`")

# ----------------- 単回帰・重回帰 -----------------
cols1, cols2 = st.columns(2)

# ---------- 左カラム：温度・VPD ----------
with cols1:
    # 温度 × 収量
    st.markdown("### 温度と収量（単回帰）")

    df_temp = df.dropna(subset=["mean_temp", "mean_kg"])
    if len(df_temp) >= 3:
        X_t = sm.add_constant(df_temp[["mean_temp"]])
        y_t = df_temp["mean_kg"]

        model_temp = sm.OLS(y_t, X_t).fit()
        beta0 = float(model_temp.params.get("const", 0.0))
        beta1 = float(model_temp.params["mean_temp"])

        st.markdown(
            f"- 回帰式: `収量 = {beta0:.1f} + {beta1:.2f} × 温度`"
        )
        st.markdown(f"- 決定係数 R² = `{model_temp.rsquared:.3f}`")

        # 散布図＋回帰線（Altair）
        chart_df = df_temp.copy()
        scatter = (
            alt.Chart(chart_df)
            .mark_circle(size=80)
            .encode(
                x=alt.X("mean_temp:Q", title="平均温度[℃]"),
                y=alt.Y("mean_kg:Q", title="平均収量[kg]"),
                color=alt.Color("farm:N", title="農場"),
                tooltip=["farm", "month", "mean_temp", "mean_humid", "mean_kg"],
            )
        )
        line = (
            alt.Chart(chart_df)
            .transform_regression(
                "mean_temp",
                "mean_kg",
                method="linear",
                as_=["mean_temp", "pred_kg"],
            )
            .mark_line()
            .encode(x="mean_temp:Q", y="pred_kg:Q")
        )
        st.altair_chart(scatter + line, width="stretch")
    else:
        st.info("温度と収量の回帰を行うにはデータが足りません。")

    # VPD × 収量
    st.markdown("### VPD と収量（単回帰）")

    df_vpd = df[["mean_vpd_kpa", "mean_kg"]].dropna()
    if len(df_vpd) < 2:
        st.info("VPD と収量の回帰を行うにはデータ点が足りません。")
    else:
        X_v = sm.add_constant(df_vpd[["mean_vpd_kpa"]])
        y_v = df_vpd["mean_kg"]

        model_vpd = sm.OLS(y_v, X_v).fit()
        a = float(model_vpd.params.get("const", 0.0))
        b = float(model_vpd.params["mean_vpd_kpa"])
        r2_v = model_vpd.rsquared

        st.markdown(
            f"- 回帰式: `収量 = {a:.1f} + {b:.2f} × VPD(kPa)`"
        )
        st.markdown(f"- 決定係数 R² = `{r2_v:.3f}`")

        df_line_v = pd.DataFrame(
            {
                "mean_vpd_kpa": df_vpd["mean_vpd_kpa"],
                "pred": model_vpd.predict(X_v),
            }
        )

        scatter_v = (
            alt.Chart(df_vpd)
            .mark_circle(size=60)
            .encode(
                x=alt.X("mean_vpd_kpa:Q", title="平均 VPD(kPa)"),
                y=alt.Y("mean_kg:Q", title="平均収量[kg]"),
                tooltip=["mean_vpd_kpa", "mean_kg"],
            )
        )
        line_v = (
            alt.Chart(df_line_v)
            .mark_line()
            .encode(x="mean_vpd_kpa:Q", y="pred:Q")
        )

        st.altair_chart(scatter_v + line_v, width="stretch")

# ---------- 右カラム：湿度 ＋ 重回帰 ----------
with cols2:
    # 湿度 × 収量
    st.markdown("### 湿度と収量（単回帰）")

    df_humid = df.dropna(subset=["mean_humid", "mean_kg"])
    if len(df_humid) >= 3:
        X_h = sm.add_constant(df_humid[["mean_humid"]])
        y_h = df_humid["mean_kg"]

        model_humid = sm.OLS(y_h, X_h).fit()
        beta0_h = float(model_humid.params.get("const", 0.0))
        beta1_h = float(model_humid.params["mean_humid"])

        st.markdown(
            f"- 回帰式: `収量 = {beta0_h:.1f} + {beta1_h:.2f} × 湿度`"
        )
        st.markdown(f"- 決定係数 R² = `{model_humid.rsquared:.3f}`")

        st.line_chart(
            df_humid.set_index("mean_humid")["mean_kg"]
        )
    else:
        st.info("湿度と収量の回帰を行うにはデータが足りません。")

    # 温度＋湿度 × 収量（重回帰）
    st.markdown("### 温度＋湿度と収量（重回帰）")

    required_cols = {"mean_temp", "mean_humid", "mean_kg"}
    if required_cols.issubset(df.columns):
        df_multi = df.dropna(subset=list(required_cols))
        if len(df_multi) >= 3:
            X_m = sm.add_constant(df_multi[["mean_temp", "mean_humid"]])
            y_m = df_multi["mean_kg"]

            model_multi = sm.OLS(y_m, X_m).fit()
            params = model_multi.params
            beta0_m = float(params.get("const", 0.0))
            beta_temp = float(params.get("mean_temp", 0.0))
            beta_humid_m = float(params.get("mean_humid", 0.0))

            st.markdown(
                f"- 回帰式: `収量 = {beta0_m:.1f} + "
                f"{beta_temp:.2f} × 温度 + {beta_humid_m:.2f} × 湿度`"
            )
            st.markdown(
                f"- 決定係数 R² = `{model_multi.rsquared:.3f}`"
            )

            st.write("係数の一覧（切片・温度・湿度）")
            st.dataframe(params.to_frame("coef"))
        else:
            st.info(
                "有効なデータ（欠損除去後）が少なすぎて重回帰が計算できません。"
            )
    else:
        st.info(
            "重回帰には 'mean_temp', 'mean_humid', 'mean_kg' の3列が必要です。"
        )

