# main.py
import streamlit as st
from app.core.auth import login_form, is_logged_in, logout_button
from app.core.db import init_db

st.set_page_config(page_title="Heartful Agri Compass", layout="wide")

@st.cache_resource
def boot():
    init_db()

boot()

st.title("Heartful Agri Compass")

if is_logged_in():
    st.success(f"ログイン中：{st.session_state.get('username')}")
    st.write("左のメニューから各ページを開いてください")
    logout_button()
else:
    login_form()

