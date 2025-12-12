from pathlib import Path
from sqlalchemy import create_engine

# /home/matsuoka/work-automation/heartful-agri-compassを指すはず
ROOT_DIR = Path("/home/matsuoka/work-automation/heartful-agri-compass")

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
