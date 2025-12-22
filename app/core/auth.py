# app/core/auth.py
import streamlit as st

VALID_USERS = {
    "admin": "password123",
    "teppei": "heartful2025",
}

SESSION_KEY_LOGGED_IN = "logged_in"
SESSION_KEY_USERNAME = "username"

def login_form():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("ログイン"):
        if VALID_USERS.get(username) == password:
            st.session_state[SESSION_KEY_LOGGED_IN] = True
            st.session_state[SESSION_KEY_USERNAME] = username
            st.rerun()
        else:
            st.error("ユーザー名またはパスワードが違います")

def is_logged_in():
    return st.session_state.get(SESSION_KEY_LOGGED_IN, False)

def logout_button():
    if is_logged_in():
        if st.button("ログアウト"):
            st.session_state.clear()
            st.rerun()

