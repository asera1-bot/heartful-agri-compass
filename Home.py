import streamlit as st

from app.core.auth import login_form, is_logged_in, logout_button
from app.core.db import init_db

st.set_page_config(page_title="Heartful Agri Compass", layout="wide")
st.title("Heartful Agri Compass")

# 起動中にDBだけは必ず初期化（テーブル作成など）
init_db()

if is_logged_in():
    username = st.session_state.get("username", "")
    st.success(f"ログイン中: {username}")

    # ログアウトはサイドバーに固定
    with st.sidebar:
        logout_button()
    if n == 0:
        st.info("まず CSV Upload でデータを登録してください。")
        st.write("左のメニューから **csv upload** を開いて登録すると、 Compass / Search List に反映されます。")
    else:
        st.write("左のメニューから **Compass / Search List / csv upload** を開けます。")

else:
    st.info("ログインしてください。")
    login_form()
