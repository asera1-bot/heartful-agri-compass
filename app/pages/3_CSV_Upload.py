import streamlit as st

from core.auth import require_login

require_login()

st.title("CSV Upload")
st.write("ここに CSV アップロード　+ ETL 呼び出し機能を実装していきます。")

uploaded_file = st.file_uploader("CSV ファイルを選択してください", type=["csv"])

if uploaded_file is not None:
    st.success("とりあえずアップロードまでは成功しています（まだDBには書き込みません）。")
