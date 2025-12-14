from pathlib import Path
import sys
import pandas as pd
from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.db import get_engine
engine = get_engine()

inbox_dir = BASE_DIR / "data" / "inbox" / "harvest"

ENC_CANDIDATES = ["cp932", "utf-8-sig", "utf-8", "utf-16le"]

def ensure_raw_csv_table() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS raw_csv (
        c1 TEXT, -- 収穫日(元)
        c2 TEXT, -- 企業名
        c3 TEXT, -- 作物
        c4 TEXT  -- 収穫量(g) ※まずはTEXTで受けて後段でREAL化
    );
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)

def ensure_harvest_fact_table() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS harvest_fact (
        id           INTEGER PRIMARY KEY,
        harvest_date TEXT NOT NULL,   -- YYYY-MM-DD
        company      TEXT NOT NULL,
        crop         TEXT NOT NULL,
        amount_kg    REAL NOT NULL
    );
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)

def ensure_harvest_import_log_table() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS harvest_import_log (
      id          INTEGER PRIMARY KEY,
      path        TEXT NOT NULL UNIQUE,
      imported_at TEXT NOT NULL
    );
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)

def has_been_imported(path: Path) -> bool:
    sql = "SELECT 1 FROM harvest_import_log WHERE path = :path LIMIT 1;"
    with engine.begin() as conn:
        row = conn.execute(text(sql), {"path": str(path)}).fetchone()
    return row is not None

def mark_imported(path: Path) -> None:
    sql = """
    INSERT OR IGNORE INTO harvest_import_log(path, imported_at)
    VALUES(:path, datetime('now'));
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {"path": str(path)})

def read_harvest_csv(path: str) -> pd.DataFrame:
    p = Path(path)
    last_err = None

    for enc in ENC_CANDIDATES:
        try:
            df = pd.read_csv(p, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue

        df.columns = [str(c).strip() for c in df.columns]

        col_date = col_company = col_crop = col_amount = None
        for c in df.columns:
            name = c
            if ("収穫日" in name) or ("日付" in name):
                col_date = c
            if ("企業名" in name) or ("会社名" in name):
                col_company = c
            if ("収穫野菜名" in name) or ("品目" in name) or ("作物" in name):
                col_crop = c
            if ("収穫量" in name) or ("量" in name) or ("ｇ" in name) or ("g" in name):
                col_amount = c

        if any(v is None for v in [col_date, col_company, col_crop, col_amount]):
            continue

        out = df[[col_date, col_company, col_crop, col_amount]].copy()
        out = out.rename(columns={col_date: "c1", col_company: "c2", col_crop: "c3", col_amount: "c4"})
        out = out.dropna(subset=["c1", "c2", "c3", "c4"])
        return out

    raise ValueError(f"{p.name}: ヘッダ特定/文字コード判定に失敗しました。最後のエラー: {last_err}")

def import_harvest_csv(path: str) -> None:
    ensure_raw_csv_table()
    ensure_harvest_import_log_table()

    p = Path(path)
    if has_been_imported(p):
        print(f"[SKIP] すでに取り込み済み: {p.name}")
        return

    df = read_harvest_csv(str(p))
    with engine.begin() as conn:
        df.to_sql("raw_csv", conn, if_exists="append", index=False)

    mark_imported(p)
    print(f"[OK] raw_csv 追加: {p.name} rows={len(df)}")

def upsert_raw_to_harvest_fact() -> int:
    ensure_harvest_fact_table()

    # ★ 日付の正規化：
    # - "YYYY/MM/DD" -> "YYYY-MM-DD"
    # - Excelシリアルっぽい数字 -> 1899-12-30起点で日付化
    sql = """
    INSERT INTO harvest_fact (harvest_date, company, crop, amount_kg)
    SELECT
      CASE
        WHEN trim(c1) GLOB '[0-9][0-9][0-9][0-9]/[0-9]*/*' THEN date(replace(trim(c1), '/', '-'))
        WHEN trim(c1) GLOB '[0-9]*' THEN date('1899-12-30', '+' || CAST(trim(c1) AS INTEGER) || ' days')
        ELSE date(trim(c1))
      END AS harvest_date,
      trim(c2) as company,
      trim(c3) as crop,
      CAST(c4 as REAL) / 1000.0 as amount_kg
    FROM raw_csv r
    WHERE
      (CASE
        WHEN trim(c1) GLOB '[0-9][0-9][0-9][0-9]/[0-9]*/*' THEN date(replace(trim(c1), '/', '-'))
        WHEN trim(c1) GLOB '[0-9]*' THEN date('1899-12-30', '+' || CAST(trim(c1) AS INTEGER) || ' days')
        ELSE date(trim(c1))
      END) IS NOT NULL
      AND trim(c2) IS NOT NULL AND trim(c2) <> ''
      AND trim(c3) IS NOT NULL AND trim(c3) <> ''
      AND c4 IS NOT NULL
      AND NOT EXISTS(
        SELECT 1 FROM harvest_fact f
        WHERE
          f.harvest_date = (CASE
            WHEN trim(r.c1) GLOB '[0-9][0-9][0-9][0-9]/[0-9]*/*' THEN date(replace(trim(r.c1), '/', '-'))
            WHEN trim(r.c1) GLOB '[0-9]*' THEN date('1899-12-30', '+' || CAST(trim(r.c1) AS INTEGER) || ' days')
            ELSE date(trim(r.c1))
          END)
          AND f.company = trim(r.c2)
          AND f.crop = trim(r.c3)
          AND f.amount_kg = CAST(r.c4 as REAL) / 1000.0
      );
    """
    with engine.begin() as conn:
        res = conn.execute(text(sql))
        return res.rowcount if res.rowcount is not None else -1

if __name__ == "__main__":
    if not inbox_dir.exists():
        raise FileNotFoundError(f"inbox/harvest ディレクトリがありません: {inbox_dir}")

    targets = sorted(p for p in inbox_dir.glob("*.csv") if not p.name.endswith(":Zone.Identifier"))
    if not targets:
        raise FileNotFoundError(f"{inbox_dir} に収穫CSVが見つかりません。")

    print(f"{len(targets)} ファイルを処理します。")
    for path in targets:
        import_harvest_csv(str(path))

    added = upsert_raw_to_harvest_fact()
    print(f"[OK] harvest_fact へ追加: {added}行")

