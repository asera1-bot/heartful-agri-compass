import streamlit as st
from app.core.auth import login_form, is_logged_in, logout_button

st.set_page_config(page_title="Heartful Agri Compass", layout="wide")

st.title("Heartful Agri Compass")

if is_logged_in():
    st.success(f"ログイン中: {st.session_state_get('username')}")
    st.write("左のメニューから Compass / SearchList / CSV Upload を開けます。")
    logout_button()
else:
    st.info("ログインしてください。")
    login_form()
