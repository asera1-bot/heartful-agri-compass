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

    # DBの現状をここで「見える化」しておくと、Cloud/Local差分の切り分けが一瞬でできる
    try:
        n = table_count("harvest_fact")
    except Exception as e:
        st.error("DBの状態確認に失敗しました。(接続バス/初期化を確認)")
        st.exception(e)
        st.stop()

    st.caption(f"harvest_fact 件数: {n}")

    if n == 0:
        st.info("まず CSV Upload でデータを登録してください。")
        st.write("左のメニューから **csv upload** を開いて登録すると、 Compass / Search List に反映されます。")
    else:
        st.write("左のメニューから **Compass / Search List / csv upload** を開けます。")

else:
    st.info("ログインしてください。")
    login_form()
