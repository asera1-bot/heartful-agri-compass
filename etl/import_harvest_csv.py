from pathlib import Path
import sys
import re
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text

# --------------------
# Path / Engine
# --------------------
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.db import get_engine
engine = get_engine()

INBOX_DIR = BASE_DIR / "data" / "inbox" / "harvest"
EXCEL_EPOCH = datetime(1899, 12, 30)

# --------------------
# Schema
# --------------------
def ensure_raw_csv_table():
    sql = """
    CREATE TABLE IF NOT EXISTS raw_csv (
        c1 TEXT,         -- date raw
        c2 TEXT,         -- company raw
        c3 TEXT,         -- crop raw
        c4 TEXT,         -- amount raw
        source_file TEXT -- file name
    );
    """
    with engine.begin() as c:
        c.execute(text(sql))

def ensure_harvest_fact_table():
    sql = """
    CREATE TABLE IF NOT EXISTS harvest_fact (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        harvest_date TEXT NOT NULL,  -- YYYY-MM-DD
        company      TEXT NOT NULL,
        crop         TEXT NOT NULL,
        amount_kg    REAL NOT NULL,
        source_file  TEXT,
        UNIQUE(harvest_date, company, crop, amount_kg, source_file)
    );
    """
    with engine.begin() as c:
        c.execute(text(sql))

def ensure_harvest_import_log_table():
    sql = """
    CREATE TABLE IF NOT EXISTS harvest_import_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE,
        imported_at TEXT NOT NULL
    );
    """
    with engine.begin() as c:
        c.execute(text(sql))

def has_been_imported(path: Path) -> bool:
    sql = "SELECT 1 FROM harvest_import_log WHERE path = :path LIMIT 1;"
    with engine.begin() as c:
        row = c.execute(text(sql), {"path": str(path)}).fetchone()
    return row is not None

def mark_imported(path: Path) -> None:
    sql = """
    INSERT OR IGNORE INTO harvest_import_log(path, imported_at)
    VALUES(:path, datetime('now'));
    """
    with engine.begin() as c:
        c.execute(text(sql), {"path": str(path)})

# --------------------
# Utils
# --------------------
ZEN_NUM  = str.maketrans("０１２３４５６７８９．，", "0123456789.,")
ZEN_DATE = str.maketrans("０１２３４５６７８９／－", "0123456789/-")

def parse_amount_to_kg(val) -> float | None:
    """
    量の正規化:
    - "1,234" / "1234g" / "1234 g" -> 1.234 (kg)
    - "1.2kg" -> 1.2 (kg)
    - 全角数字/カンマ対応
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    s = s.translate(ZEN_NUM)
    s = re.sub(r"\s+", "", s)
    s = s.replace(",", "")
    s_low = s.lower()

    # kg表記
    if "kg" in s_low:
        m = re.search(r"[-+]?\d*\.?\d+", s_low)
        return float(m.group()) if m else None

    # g表記 or 数字のみ
    m = re.search(r"[-+]?\d*\.?\d+", s_low)
    if not m:
        return None
    grams = float(m.group())
    return grams / 1000.0

def parse_harvest_date(val) -> str | None:
    """
    日付の正規化:
    - "2025/8/18" "2025/08/18" "2025-8-18" "2025-08-18"
    - 全角対応
    - Excelシリアル(30000~60000程度)
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    s = s.translate(ZEN_DATE)
    s = re.sub(r"\s+", "", s)

    # Excelシリアル
    if s.isdigit():
        n = int(s)
        if 30000 <= n <= 60000:
            return (EXCEL_EPOCH + timedelta(days=n)).date().isoformat()
        return None

    s2 = s.replace("/", "-")

    # strict first
    try:
        return datetime.strptime(s2, "%Y-%m-%d").date().isoformat()
    except ValueError:
        pass

    # pandas fallback
    try:
        dt = pd.to_datetime(s2, errors="raise")
        return dt.date().isoformat()
    except Exception:
        return None

# --------------------
# CSV read + detect columns
# --------------------
ENC_CANDIDATES = ["utf-8-sig", "utf-8", "cp932", "utf-16le"]

def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    last_err = None
    for enc in ENC_CANDIDATES:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"{path.name}: decode failed. last_err={last_err}")

def detect_columns(df: pd.DataFrame):
    df.columns = [str(c).strip() for c in df.columns]

    col_date = col_company = col_crop = col_amount = None
    for c in df.columns:
        name = str(c)

        if ("収穫日" in name) or ("日付" in name):
            col_date = c
        if ("企業名" in name) or ("会社名" in name):
            col_company = c
        if ("収穫野菜名" in name) or ("品目" in name) or ("作物" in name):
            col_crop = c
        if ("収穫量" in name) or ("ｇ" in name) or ("g" in name) or name.endswith("g") or ("量" in name):
            col_amount = c

    if any(v is None for v in [col_date, col_company, col_crop, col_amount]):
        return None
    return col_date, col_company, col_crop, col_amount


# --------------------
# Import
# --------------------
def import_all_csv():
    if not INBOX_DIR.exists():
        raise FileNotFoundError(f"{INBOX_DIR} not found")

    targets = sorted(
        p for p in INBOX_DIR.glob("*.csv")
        if not p.name.endswith(":Zone.Identifier")
    )
    if not targets:
        raise FileNotFoundError("No CSV files found")

    ensure_raw_csv_table()
    ensure_harvest_import_log_table()

    for p in targets:
        if has_been_imported(p):
            print(f"[SKIP] already imported: {p.name}")
            continue

        df = read_csv_with_fallback(p)
        cols = detect_columns(df)
        if cols is None:
            raise ValueError(f"[ERROR] header not detected: {p.name} columns={list(df.columns)}")

        col_date, col_company, col_crop, col_amount = cols

        out = df[[col_date, col_company, col_crop, col_amount]].copy()
        out = out.rename(columns={
            col_date: "c1",
            col_company: "c2",
            col_crop: "c3",
            col_amount: "c4",
        })
        out["source_file"] = p.name
        out = out.dropna(subset=["c1", "c2", "c3", "c4"])

        with engine.begin() as c:
            out.to_sql("raw_csv", c, if_exists="append", index=False)

        mark_imported(p)
        print(f"[OK] raw_csv loaded: {p.name} ({len(out)} rows)")

def upsert_raw_to_harvest_fact() -> int:
    ensure_harvest_fact_table()

    df = pd.read_sql("SELECT c1,c2,c3,c4,source_file FROM raw_csv", engine)

    df["harvest_date"] = df["c1"].apply(parse_harvest_date)
    df["company"] = df["c2"].astype(str).str.strip()
    df["crop"] = df["c3"].astype(str).str.strip()
    df["amount_kg"] = df["c4"].apply(parse_amount_to_kg)

    before = len(df)
    df = df.dropna(subset=["harvest_date", "company", "crop", "amount_kg"])

    df = df.drop_duplicates(
        subset=["harvest_date", "company", "crop", "amount_kg"]
    )

    dropped = before - len(df)
    if dropped:
        print(f"[WARN] dropped rows: {dropped}")

    rows = df[["harvest_date", "company", "crop", "amount_kg", "source_file"]].to_dict("records")

    sql = text("""
    INSERT OR IGNORE INTO harvest_fact(harvest_date, company, crop, amount_kg, source_file)
    VALUES(:harvest_date, :company, :crop, :amount_kg, :source_file)
    """)
    with engine.begin() as c:
        c.execute(sql, rows)

    return len(rows)

# --------------------
# Main
# --------------------
def run():
    import_all_csv()
    added = upsert_raw_to_harvest_fact()
    print(f"[OK] harvest_fact inserted (attempted): {added} rows")

if __name__ == "__main__":
    run()

