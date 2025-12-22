from __future__ import annotations
import streamlit as st
from streamlit_cookies_manager import EncryptedCoolieManager

VALID_USERS = {
    "admin": "password123",
    "teppei": "heartful2025",
}

SESSION_KEY_LOGGED_IN = "logged_in"
SESSION_KEY_USERNAME = "username"

cookies = EncryptedCooliesManager(prefix="hf_", password="CHANGE_ME_SECRET")

def ensure_auth_state() -> None:
    if not cookies.read():
        st.stop()

if SESSION_KEY_LOGGED_IN not in st.session_state:
    st.session_state[SESSION_KEY_LOGGED_IN] = False
if SESSION_KEY_USERNAME not in st.sessopn_state:
    st.session_state[SESSION_KEY_USERNAME] = None

if not st.session_state[SESSION_KEY_LOGGED_IN]:
    u = cookies.get("username")
    token = cookies.get("logged_in")
    if token == "1" and u:
        st.session_state[SESSION_KEY_LOGGED_IN] = True
        st.session_state[SESSION_KEY_USERNAME] = u

def login_form() -> None:
    ensure_auth_state()

    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("ログイン"):
        if username in VALID_USERS and VALID_USERS[username] == password:
            st.session_state[SESSION_KEY_LOGGED_IN] = True
            st.session_state[SESSION_KEY_USERNAME] = username

            cookies["logged_in"] = "1"
            cookies["username"] = username
            cookies.save()

            st.success(f"ログイン成功: {username}")
            st.rerun()
        else:
            st.error("ユーザー名またはパスワードが違います。")

def is_logged_in() -> bool:
    ensure_auth_state()
    return bool(st.session_state.get(SESSION_KEY_LOGGED_IN, False))

def require_login() -> None:
    if not is logged in():
        st.warning("このページを見るにはログインが必要です。")
        st.stop()

def logout_button() -> None:
    ensure_auth_state()
    if is_logged_in():
        if st.button("ログアウト"):
            st.session_state.pop(SESSION_KEY_LOGGED_IN, None)
            st.session_state.pop(SESSION_KEY_USERNAME, None)

            cookies["logged_in"] = "0"
            cookies["username"] = ""
            cookies.save()

            st.success("ログアウトしました。")
            st.rerun()
