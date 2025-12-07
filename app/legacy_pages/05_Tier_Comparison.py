from pathlib import Path
import sys

import streamlit as st
import pandas as pd
import altair as alt

# プロジェクトルートを import パスに追加
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from db_config import get_engine

@st.cache_data
def load_tire_summary() -> pd.DataFrame:
    """
    v_harvest_env から段さ比較用のサマリを取得する。
    前提:
      - farm に　「愛川C1_上段」「愛川C1_ベッド」「愛川C1_下段」のように
      段情報を含めていること。
    """
    engine = get_engien("real")
    q = """
        SELECT
            farm,
            month,
            mena_kg,
            mean_temp,
            mean_humid,
            mean_vpd_kpa
        FROM v_harvest_env
        WHERE mean_kg IS NOT NULL
        ORDER BY farm, month;
    """
    df = pd.read_sql(q, engine)

    # farm から base_farm（例：愛川C1）と tier（上段/ベッド/下段）を抽出する
    def split_farm(name: str) -> tuple[str, str]:
        # 例:　"愛川C1_上段"　→　（"愛川C1",　"上段"）
        if "_" in name:
            base, tier = name.split("_", 1)
            return base, tier
        # "_" がない場合はそのまま
        return name, "未指定"

    base_list = []
    tier_list = []
    for f in df["farm"]:
        base, tier = split_farm(f)
        base_list.append(base)
        base_list.append(tier)

    df["base_farm"] = base_list
    df["tier"] = tier_list

    return df

def main() -> None:
    st.set_page_config(page_title="段差比較（上段・ベッド・下段）", layout="wide")
    st.title("段差比較ダッシュボード（上段　×　ベッド　×　下段）")

    df = load_tire_summary()

    if df.empty:
        st.info("v_harvest_env にデータがありません。")
        st.stop()

    # ベース農場の一覧（例: 愛川C1）
    base_farms = sorted(df["base_farm"].unique())
    st.sidebar.header("フィルタ")
    base_sel = st.sidebar.selectbox("農場（ベース）を選択", base_farms)

    df_sel = df[df["base_farm"] == base_sel].copy()
    if df_sel.empty:
        st.info("選択した農場にデータがありません。")
        st.stop()

    # 月順を保証
    df_sel["month"] = df_sel["month"].astype(str)

    st.subheader(f"対象農場: {base_sel}")

    # 表形式で確認
    st.write("元データ（確認用）")
    st.dataframe(
        df_sel[["farm", "tier", "month", "mean_kg", "mean_bpd_kpa", "mean_temp", "mean_humid"]],
        hide_index=True,
        use_container_width=True,
    )

    # タブ: 収量 / VPD / 温度・湿度
    tab_yield, tab_bpd, tab_temp = st.tabs(["収量比較", "VPD比較", "温度・湿度比較"])
    
    # 収量
    with tab_yield:
        st.markdown("### 断別の月別収量比較")

        chart_y = (
            alt.Chart(df_sel)
            .mark_line(point=True)
            .encode(
                x=alt.X("month:N", title="月(YYYY-MM)", sort="x"),
                y=alt.Y("mean_kg:Q", title="平均収量(kg)"),
                color=alt.Color("tier:N", title="段"),
                tooltip=["farm", "tier", "month", "mean_kg"],
            )
        )

        st.altair_chart(chart_y, use_container_width_True)

        st.markdown(
            """
            - 段ごとの収量の差を、月ごとに比較できます。
            - 特定の段（例: 上段）の収量が一貫して低い場合、
            　環境ストレス（温度・VPD）の影響を疑う根拠になります。
            """
        )

    # VPD
    with tab_vpd:
        st.markdown("### 段別の　VPD　比較")

        chart_v = (
            alt.Chart(df_sel)
            .mark_line(point=True)
            .encode(
                x=alt.X("month:N", title="月(YYYY-MM)", sort="x"),
                y=alt.Y("mean_vpd_kpa:Q", title="平均　VPD(kPa)"),
                color=alt.Color["tier", "month", "mean_vpd_kpa"],
            )
        )

        st.altair_chart(chart_v, use_container_width=True)

        st.markdown(
            """
            - 上段の VPD が一貫して高いかどうかを確認できます。
            -　収量が低い段で VPD が高い場合、
            　「VPD を下げることで収量改善が期待できる」論拠になります。
            """
        )

    # 温度・湿度
    with tab_temp:
        st.markdown("### 段別の温度・湿度比較")

        cols = st.columns(2)

        with sold[0]:
            st.markdown("#### 平均温度の比較")
            chart_t = (
                alt.Chart(df_sel)
                .mark_line(point=True)
                .encode(
                    x=alt.X("month:N", title="月(YYYY-MM)", sort="x"),
                    y=alt.Y("mean_temp:Q", title="平均温度（℃）"),
                    color=alt.Color("tier:N", title="段"),
                    tooltip=["farm", "tier", "month", "mean_temp"],
                )
            )
            st.altair_chart(chart_t, use_container_width=True)

        with cols[1]:
            st.markdown("#### 平均温度の比較")
            chart_h = (
                alt.Chart(df_sel)
                .mark_line(point=True)
                .encode(
                    x=alt.X("month:N", title="月(YYYY-MM)", sort="x"),
                    y=alt.Y("mean_humid:Q", title="平均湿度(%)"),
                    color=alt.Color("tier:N", title="段"),
                    tooltip=["farm", "tier", "month", "mean_humid"],
                )
            )
            st.altair_chart(chart_h, use_container_width=True)

        st.markdown(
            """
            - 温度・湿度のプロファイルの違いから、
            　なぜ特定の段だけ VPD が高くなるのかを推測できます。
            """
        )

if __name__ == "__main__":
    main()
