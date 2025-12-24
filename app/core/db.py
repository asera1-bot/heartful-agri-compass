# app/core/db.py
from pathlib import Path
from sqlalchemy import create_engine
from common.constants import DB_PATH

# DB パス（相対・Cloud対応）
DB_PATH = Path(__file__).resolve().parents[2] / "db" / "heartful_dev.db"

def get_engine():
    return create_engine(
        f"sqlite:///{DB_PATH}",
        future=True,
    )

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine()
    with engine.begin() as conn:
        # harvest_fact（分析用・重複防止）
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS harvest_fact (
            harvest_date TEXT NOT NULL,
            company      TEXT NOT NULL,
            crop         TEXT NOT NULL,
            amount_kg    REAL NOT NULL,
            source_file  TEXT,
            UNIQUE(harvest_date, company, crop, amount_kg)
        );
        """)

        # raw_csv（生データ保存）
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS raw_csv (
            c1 TEXT,
            c2 TEXT,
            c3 TEXT,
            c4 REAL,
            source_file TEXT
        );
        """)

