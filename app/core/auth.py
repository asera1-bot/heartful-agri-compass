from __future__ import annotations
import streamlit as st

SESSION_KEY_LOGGED_IN =  "logged_in"
SESSION_KEY_USERNAME = "username"

def _get_users() -> dict[str, str]:
    if "users" in st.secrets:
        return dict(st.secrets["users"])
    return{
            "admin": "password123",
            "teppei": "186125C",
        }

def login_form() -> None:
    st.subheader("Login")
    username = st.text_input("Username").strip()
    password = st.text_input("Password", type="password").strip()

    if st.button("ログイン"):
        users = _get_users()
        if username in users and users[username] == password:
            st.session_state[SESSION_KEY_LOGGED_IN] = True
            st.session_state[SESSION_KEY_USERNAME] = username
            st.success(f"ログイン成功: {username}")
            st.rerun()
        else:
            st.error("ユーザー名またはパスワードが違います。")

def is_logged_in() -> bool:
    return bool(st.session_state.get(SESSION_KEY_LOGGED_IN, False))

def require_login() -> None:
    if not is_logged_in():
        st.warning("このページを見るにはログインが必要です。")
        st.stop()

def logout_button() -> None:
    if is_logged_in() and st.button("ログアウト"):
        st.session_state.pop(SESSION_KEY_LOGGED_IN, None)
        st.session_state.pop(SESSION_KEY_USERNAME, None)
        st.rerun()
