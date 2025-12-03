from pathlib import Path
from sqlalchemy import create_engine
from aqlalchemy.engine import Engine

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "db" / "heartful_dev.db"

_eingine: Engine | None = None

def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlit:///{DB_PATH}", future=True)
    return _engine
