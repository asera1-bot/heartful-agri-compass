import sys
from pathlib import Path
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.auth import login_form, is_logged_in, logout_button
from core.db import init_db

st.set_page_config(page_title="Heartful Agri Compass", layout="wide")

@st.cache_resource
def boot():
    init_db()

boot()

st.title("Heartful Agri Compass")

if is_logged_in():
    st.success(f"ログイン中: {st.sessoin_state.get('username')}")
    st.write("左のページから Compass / Search / CSV Upload を開けます。")
    logout_button()
else:
    st.info("ログインしてください。")
    login_form()
