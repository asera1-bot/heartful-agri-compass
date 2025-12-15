from __future__ import annotations
import streamlit as st

VALID_USERS = {
    "admin": "password123",
    "teppei": "heartful2025",
}

SESSION_KEY_LOGGED_IN = "logged_in"
SESSION_KEY_USERNAME = "username"

def login_form() -> None:
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("ログイン"):
        if username in VALID_USERS and VALID_USERS[username] == password:
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
    if is_logged_in():
        if st.button("ログアウト"):
            st.session_state.pop(SESSION_KEY_LOGGED_IN, None)
            st.session_state.pop(SESSION_KEY_USERNAME, None)
            st.success("ログアウトしました。")
            st.rerun()

