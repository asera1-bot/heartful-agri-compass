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
def load_brand_monthly() -> pd.DataFrame:
    """
    v_brand_monthly から ブランド別の月次収量を取得する。
    farm_group カラムが無い場合は仮に 'Unknown' を補う。
    """
    engine = get_engine("real")
    q = """
        SELECT
            brand_code,
            farm_group,
            category,
            crop_code,
            crop_name_ja,
            brand_name_ja,
            month,
            total_kg
        FROM v_brand_monthly
        ORDER BY month;
    """
    df = pd.read_sql(q, engine)

    # 安全弁：farm_group カラムが無い or 全部 NULL だった場合の保険
    if "farm_group" not in df.columns:
        df["farm_group"] = "Unknown"
    else:
        if df["farm_group"].isna().all():
            df["farm_group"] = "Unknown"

    return df


def main() -> None:
    st.set_page_config(page_title="ブランド別月次収量", layout="wide")
    st.title("ブランド別 月次収量ダッシュボード")

    df = load_brand_monthly()

    # デバッグ用
    st.write("DEBUG columns:", list(df.columns))

    if df.empty:
        st.info("v_brand_monthly にデータがありません。")
        st.stop()

    # 月は文字列にそろえる
    df["month"] = df["month"].astype(str)

    # ===== サイドバーのフィルタ =====
    st.sidebar.header("フィルタ")

    # ここは「farm_group」カラムから、Python 変数 farm_groups を作る
    farm_groups = sorted(df["farm_group"].dropna().unique())
    farm_group_sel = st.sidebar.multiselect(
        "農園（farm_group）を選択",
        farm_groups,
        default=farm_groups or None,
    )
    if farm_group_sel:
        df = df[df["farm_group"].isin(farm_group_sel)]

    categories = sorted(df["category"].dropna().unique())
    category_sel = st.sidebar.multiselect(
        "カテゴリーを選択（FRUIT / LEAF 等）",
        categories,
        default=categories or None,
    )
    if category_sel:
        df = df[df["category"].isin(category_sel)]

    crops = sorted(df["crop_name_ja"].dropna().unique())
    crop_sel = st.sidebar.multiselect(
        "作物名を選択（いちご・ミニトマトなど）",
        crops,
        default=crops or None,
    )
    if crop_sel:
        df = df[df["crop_name_ja"].isin(crop_sel)]

    if df.empty:
        st.info("選択された条件に一致するデータがありません。")
        st.stop()

    # ===== 一覧表示 =====
    df_display = df[
        [
            "farm_group",
            "category",
            "crop_name_ja",
            "brand_name_ja",
            "brand_code",
            "month",
            "total_kg",
        ]
    ].copy()

    st.subheader("月次収量一覧")
    st.dataframe(df_display, width="stretch", hide_index=True)

    # ===== グラフタブ =====
    tab_brand, tab_category, tab_crop = st.tabs(
        ["ブランド別推移", "カテゴリー別合計", "作物別推移"]
    )

    # 1) ブランド別の月次推移
    with tab_brand:
        st.markdown("### ブランド別 月次収量推移（brand_code単位）")

        chart_brand = (
            alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x=alt.X("month:N", title="月(YYYY-MM)", sort="x"),
                y=alt.Y("total_kg:Q", title="収量(kg)"),
                color=alt.Color("brand_code:N", title="ブランドコード"),
                tooltip=[
                    "farm_group",
                    "category",
                    "crop_name_ja",
                    "brand_name_ja",
                    "brand_code",
                    "month",
                    "total_kg",
                ],
            )
        )
        st.altair_chart(chart_brand, width="stretch")

    # 2) カテゴリー別（FRUIT / LEAF）の月次合計
    with tab_category:
        st.markdown("### カテゴリー別 月次収量合計（FRUIT / LEAF など）")

        df_cat = (
            df.groupby(["farm_group", "category", "month"], as_index=False)
            .agg(total_kg=("total_kg", "sum"))
        )

        chart_cat = (
            alt.Chart(df_cat)
            .mark_line(point=True)
            .encode(
                x=alt.X("month:N", title="月(YYYY-MM)", sort="x"),
                y=alt.Y("total_kg:Q", title="収量(kg)"),
                color=alt.Color("category:N", title="カテゴリー"),
                tooltip=["farm_group", "category", "month", "total_kg"],
            )
        )
        st.altair_chart(chart_cat, width="stretch")

    # 3) 作物別（いちご・ミニトマトなど）の推移
    with tab_crop:
        st.markdown("### 作物別 月次収量推移")

        df_crop = (
            df.groupby(["farm_group", "crop_name_ja", "month"], as_index=False)
            .agg(total_kg=("total_kg", "sum"))
        )

        chart_crop = (
            alt.Chart(df_crop)
            .mark_line(point=True)
            .encode(
                x=alt.X("month:N", title="月(YYYY-MM)", sort="x"),
                y=alt.Y("total_kg:Q", title="収量(kg)"),
                color=alt.Color("crop_name_ja:N", title="作物名"),
                tooltip=["farm_group", "crop_name_ja", "month", "total_kg"],
            )
        )
        st.altair_chart(chart_crop, width="stretch")


if __name__ == "__main__":
    main()

