import streamlit as st

SESSION_KEY_LOGGED_IN = "logged_in"
SESSION_KEY_USERNAME = "username"

def _users():
    # secrets.toml の [users] を読む
    return dict(st.secrets.get("users", {}))

def login_form():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("ログイン"):
        users = _users()
        if users.get(username) == password:
            st.session_state[SESSION_KEY_LOGGED_IN] = True
            st.session_state[SESSION_KEY_USERNAME] = username
            st.rerun()
        else:
            st.error("ユーザー名またはパスワードが違います。")

def is_logged_in():
    return bool(st.session_state.get(SESSION_KEY_LOGGED_IN, False))

def require_login():
    if not is_logged_in():
        st.warning("このページを見るにはログインが必要です。")
        st.stop()

def logout_button():
    if is_logged_in() and st.button("ログアウト"):
        st.session_state.clear()
        st.rerun()

