# main.py (repo root)  --- DIAG MODE ---
import os, sys
from pathlib import Path
import streamlit as st

st.write("CWD:", os.getcwd())
st.write("FILE:", __file__)
st.write("sys.version:", sys.version)
st.write("sys.path[:15]:", sys.path[:15])

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app"
st.write("ROOT:", str(ROOT), "exists:", ROOT.exists())
st.write("APP_DIR:", str(APP_DIR), "exists:", APP_DIR.exists())
st.write("app/__init__.py exists:", (APP_DIR / "__init__.py").exists())
st.write("app/core/auth.py exists:", (APP_DIR / "core" / "auth.py").exists())

# app を import してみる（ここが通るかで確定）
try:
    import app
    st.success(f"import app OK: {app.__file__}")
except Exception as e:
    st.error("import app FAILED")
    st.exception(e)
    st.stop()

# app.core.auth を import
try:
    from app.core.auth import login_form, is_logged_in, logout_button
    st.success("from app.core.auth import ... OK")
except Exception as e:
    st.error("from app.core.auth import ... FAILED")
    st.exception(e)
    st.stop()

st.info("DIAG finished. imports are OK.")

