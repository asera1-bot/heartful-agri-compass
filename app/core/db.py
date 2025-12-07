from pathlib import Path
from sqlalchemy import create_engine

# プロジェクトルートを指定
ROOT_DIR = Path(__file__).resolve().parents[2]

# db ディテクトリを保障
DB_DIR = ROOT_DIR / "db"
DB_DIR.mkdir(exist_ok=True)

# SQLite　のパス
DB_PATH = DB_DIR / "heartful_dev.db"

_engine = None

def get_engine():
    """
    アプリ全体で共通して使う SQLite Engine を使す。
    最初の呼び出し時に Engine を作成し、以降は使いまわす。
    """
    global _engine

    if _engine is None:
        _engine = create_engine(f"sqlite://{DB_PATH}", future=True)

    return _engine
