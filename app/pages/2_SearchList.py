import streamlit as st

from core.auth import require_login

require_login()

st.title("Search / List")
st.write("ここに収量データなどの検索・一覧画面を実装していきます。")
st.caption("※現在はぴレースホルダーです。")
