# app/main.py
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]  # = リポジトリ直下
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from app.core.auth import login_form, is_logged_in, logout_button

st.set_page_config(page_title="Heartful Agri Compass", layout="wide")

def main():
    st.title("Heartful Agri Compass")
    if is_logged_in():
        st.success(f"ログイン中：{st.session_state.get('username')}")
        st.write("左のページから Compass / Search / CSV Upload を開けます。")
        logout_button()
    else:
        st.info("ログインしてください。")
        login_form()

if __name__ == "__main__":
    main()

