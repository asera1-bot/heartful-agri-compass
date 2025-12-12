import sys, os
ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
sys.path.append(PARENT)


import streamlit as st

from core.auth import login_form, is_logged_in, logout_button

st.set_page_config(
    page_title="Heartful Agri Compass",
    layout="wide",
)

def main() -> None:
    st.title("Heartful Agri Compass")

    if is_logged_in():
        st.success(f"ログイン中：{st.session_state.get('username')}")
        st.write("左のページから Compass / Search / CSV Upload を開けます。")
        st.caption("※　この Home はログイン状態の確認用です。")
    else:
        st.info("ログインしてください。")
        login_form()

if __name__ == "__main__":
    main()
