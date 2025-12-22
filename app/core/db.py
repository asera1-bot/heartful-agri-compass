from pathlib import Path
from sqlalchemy import create_engine
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
    global _engine

    if _engine is None:
        # デバック用ログ（必要なければ後で消してOK)
        print(f"[DB DEBUG] DB_PATH = {DB_PATH} (exists={DB_PATH.exists()}")

        # ファイルが無ければ空のファイルだけ作成（SQLite側でテーブル作成）
        if not DB_PATH.exists():
            DB_PATH.touch()

        _engine = create_engine(
            f"sqlite:///{DB_PATH}",
            future=True,
        )

    return _engine

def init_db():
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS harvest_fact(
            harvest_date TEXT NOT NULL,
            company TEXT NOT NULL,
            crop TEXT NOT NULL,
            amount_kg REAL NOT NULL,
            source_file TEXT,
            UNIQUE(hravest_date, company, crop, amount_kg)
        )
        """)
