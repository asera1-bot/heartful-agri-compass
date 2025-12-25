# Home.py (project root)
from __future__ import annotations

import streamlit as st

from app.core.auth import login_form, is_logged_in, logout_button
from app.core.db import init_db

st.set_page_config(page_title="Heartful Agri Compass", layout="wide")

@st.cache_resource
def boot():
    # DBファイル作成・テーブル作成など「起動時に1回だけ」やりたい処理
    init_db()

boot()

st.title("Heartful Agri Compass")
st.caption("収量データの登録 → 可視化（Compass） → 検索（Search/List）")

if is_logged_in():
    user = st.session_state.get("username", "(unknown)")
    st.success(f"ログイン中: {user}")

    st.write("左のメニューからページを選択してください。")
    st.write("（もし左メニューが見えない場合：画面左上の「＞」でサイドバーを開いてください）")

    # Streamlitのバージョンによっては page_link が使える
    try:
        st.page_link("pages/1_Compass.py", label="➡️ Compass（全体傾向）")
        st.page_link("pages/2_Search_list.py", label="➡️ Search / List（検索・DL）")
        st.page_link("pages/3_csv_upload.py", label="➡️ CSV Upload（登録）")
    except Exception:
        # 旧バージョン向け（リンクが効かない環境もあるので案内だけ）
        st.info("ページ移動は左メニューから行ってください（pages/ 以下に配置）。")

    st.divider()
    logout_button()

else:
    st.info("ログインしてください。")
    login_form()

