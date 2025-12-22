from pathlib import Path
from sqlalchemy import create_engine, text
from app.common.constants import DB_PATH

# /home/matsuoka/work-automation/heartful-agri-compassを指すはず
ROOT_DIR = Path(__file__).resolve().parents[2]

# dbディテクトリ
DB_DIR = ROOT_DIR / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)

# SQLite　ファイル
DB_PATH = DB_DIR / "heartful_dev.db"

_engine = None

def get_engine():
    """アプリ全体で共通して使う SQLite Engine を返す。"""
    return create_engine(f"sqlite:///{str(DB_PATH)}", future=True)

def init_db():
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql("""
        CREATE TABLE IF EXISTS harvest_fact (
            harvest_date TEXT NOT NULL,
            company TEXT NOT NULL,
            crop TEXT NOT NULL,
            amount_kg TEXT NOT NULL,
            source_file TEXT,
            UNIQUE(harvest_date, company, crop, amount_kg)
        ):
        """)
        conn.exec_driver_sql("""
        CREATE TEBLE IF NOT EXISTS raw_csv (
            c1 TEXT, c2 TEXT, c3 TEXT, c4 REAL, source_file TEXT
        );
        """)
