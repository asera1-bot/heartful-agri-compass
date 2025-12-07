from pathlib import Path
import sys

import streamlit as st
import pandas as pd
import altair as alt

# プロジェクトルート（heartful-analytics）を import パスに追加
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from db_config import get_engine

@st.cache_data
def load_env_daily() -> pd.DataFrame:
    """
    env_daily から VPD 日次データを取得する。
    前提： env_daily(farm, date, mean_temp, mean_humidity, vpd_kpa, ...)
    """
    engine = get_engine("real")
    q = """
        SELECT
            farm,
            date,
            vpd_kpa
        FROM env_daily
        WHERE vpd_kpa IS NOT NULL
        ORDER BY date, farm;
    """
    # date を日付型にパース
    return pd.read_sql(q, engine, parse_dates=["date"])

def main() -> None:
    st.set_page_config(page_title="VPDヒートマップ", layout="wide")
    st.title("VPD　ヒートマップ（環境　×　時間）")

    df = load_env_daily()

    if df.empty:
        st.info("env_daily に VPD データがありません。")
        st.stop()

    # 月列を追加
    df["month"] = df["date"].dt.to_period("M").astype(str)

    # サイドバーでフィルタ
    st.sidebar.header("フィルタ")

    farms = sorted(df["farm"].unique())
    farm_sel = st.sidebar.multiselect("農場を選択", farms, default=farms)

    if not farm_sel:
        st.warning("少なくとも１つ農場を選択してください。")
        st.stop()

    df = df[df["farm"].isin(farm_sel)]

    # 日付範囲
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    start_date, end_date = st.sidebar.date_input(
        "期間を選択",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    # タプル　or　単体対応
    if isinstance(start_date, tuple):
        start_date, end_date = start_date

    df = df[(df["date"] >= pd.to_datetime(start_date)) &
            (df["date"] <= pd.to_datetime(end_date))]

    if df.empty:
        st.info("選択した条件に一致するデータがありません。")
        st.stop()

    st.write("データ概要", df.head())

    tab_day, tab_month = st.tabs(["日別ヒートマップ", "月別ヒートマップ"])

    # 日別　VPD　ヒートマップ
    with tab_day:
        st.subheader("日別　VPD　ヒートマップ（farm x date)")

        # Altair 用に文字列列を追加
        df_day = df.copy()
        df_day["date_str"] = df_day["date"].dt.strftime("%Y-%m-%d")

        # farm x date のヒートマップ
        chart_day = (
            alt.Chart(df_day)
            .mark_rect()
            .encode(
                x=alt.X("date_str:N", title="日付", sort="x"),
                y=alt.Y("farm:N", title="農場"),
                color=alt.Color(
                    "vpd_kpa:Q",
                    title="VPD(kPa)",
                    # スケールレンジはデフォルトに任せる（バージョン依存を避ける）
                ),
                tooltip=[
                    alt.Tooltip("famr:N", title="農場"),
                    alt.Tooltip("date_str:N", title="日付"),
                    alt.Tooltip("vpd_kpa:Q", title="VPD(kPa)", format=".2f"),
                ],
            )
        )

        st.altair_chart(chart_day, use_container_width=True)

        st.markdown(
            """
            - 色が濃いところ　= VPD　が高く、蒸散ストレスが強い日
            - VPD が **0.6～1.2 kPa** の日が多いほど、環境としては安定していると考えられます。")
            """
        )

    # 月別　VPD　ヒートマップ
    with tab_month:
        st.subheader("月別　VPD　ヒートマップ（farm x month)")

        df_month = (
            df.groupby(["farm", "month"], as_index=False)
            .agg(mean_vpd_kpa=("vpd_kpa", "mean"))
        )

        chart_month = (
            alt.Chart(df_month)
            .mark_rect()
            .encode(
                x=alt.X("month:N", title="月（YYYY-MM）", sort="x"),
                y=alt.Y("farm:N", title="農場"),
                color=alt.Color(
                    "mean_vpd_kpa:Q",
                    title="平均　VPD（kPa）",
                ),
                tooltip=[
                    alt.Tooltip("farm:N", title="農場"),
                    alt.Tooltip("month:N", title="月"),
                    alt.Tooltip("mean_vpd_kpa:Q", title="平均VPD（kPa）", format=".2f"),
                ],
            )
        )

        st.altair_chart(chart_month, use_container_width=True)

        st.markdown(
            """
            - 各月ごとの **VPD の高さ/低さ** を農場別に比較できます。
            - 収量の悪い月と、VPD が高い月が対応していないかを見ることで、
            　**どの時期に環境対策を重点化すべきか** が見えてきます。
            """
        )

if __name__ == "__main__":
    main()
