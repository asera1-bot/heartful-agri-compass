from __future__ import annotations

from sqlalchemy import create_engine, text
from app.common.constants import DB_PATH

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{str(DB_PATH)}", future=True)
        return _engine

def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

ddl_harvest_fact = """
CREATE TABLE IF NOT EXISTS harvest_fact (
    harvest_date TEXT NOT NULL,
    company      TEXT NOT NULL,
    crop         TEXT NOT NULL,
    amount_kg    REAL NOT NULL,
    source_file  TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(harvest_date, company, crop, amount_kg)
);
"""

ddl_raw_csv = """
CREATE TABLE IF NOT EXISTS raw_csv (
    c1 TEXT,
    c2 TEXT,
    c3 TEXT,
    c4 TEXT,
    source_file TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

engine = get_engine()
with engine.begin() as conn:
    conn.exec_driver_sql(ddl_harvest_fact)
    conn.exec_driver_sql(ddl_raw_csv)

def db_debug_caption(st):
    st.caption(f"DB_PATH = {DB_PATH}")
