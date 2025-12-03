from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

# === DB 接続設定(env_raw と同じ DB を想定) ===
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "db" / "harvests_real.db"
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)

# ------------------------------------------------------------
# テーブル作成
# ------------------------------------------------------------
def ensure_raw_csv_table() -> None:
    """
    収穫CSVの生データを入れる raw_csv テーブルを作成する。
    すでに存在していれば何もしない（既存スキーマを壊さない）。
    """
    ddl = """
    CREATE TABLE IF NOT EXISTS raw_csv (
        c1 TEXT, --収穫日
        c2 TEXT, --企業名
        c3 TEXT, --収穫野菜名
        c4 REAL  --収穫量(g)
    );
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)


def ensure_harvest_import_log_table() -> None:
    """
    どの収穫CSVファイルを取り込んだかを記録するログテーブル。
    同じ path の重複取り込みを防ぐ。
    """
    ddl = """
    CREATE TABLE IF NOT EXISTS harvest_import_log (
      id             INTEGER PRIMARY KEY,
      path           TEXT NOT NULL UNIQUE, -- ファイルの絶対パス
      imported_at    TEXT NOT NULL         -- 取り込み日時（SQLite の datetime('now')）
    );
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)


# ------------------------------------------------------------
# インポート済み判定 ＆ ログ記録
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# 収穫CSVの読み取り（エンコ自動判定＋ゆるいヘッダ判定）
# ------------------------------------------------------------
ENC_CANDIDATES = ["cp932", "utf-8-sig", "utf-8", "utf-16le"]


def read_harvest_csv(path: str) -> pd.DataFrame:
    """
    収穫CSV（例：2025_08_17.csv）を読み込み、
    raw_csv(c1,c2,c3,c4) 形式の DataFrame を返す。

    想定情報:
      - c1: 収穫日
      - c2: 企業名
      - c3: 収穫野菜名
      - c4: 収穫量（g）
    """
    p = Path(path)
    last_err = None

    for enc in ENC_CANDIDATES:
        try:
            df = pd.read_csv(p, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue

        # 列名を str にして前後空白を除去
        df.columns = [str(c).strip() for c in df.columns]
        cols = list(df.columns)
        print(f"[DEBUG] {p.name} encoding={enc} cols={cols}")

        # --- 日本語ヘッダ → 対応カラム名を柔軟に特定 ---
        col_date = None
        col_company = None
        col_crop = None
        col_amount = None

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

        missing = {
            "収穫日": col_date,
            "企業名": col_company,
            "収穫野菜名": col_crop,
            "収穫量": col_amount,
        }

        if any(v is None for v in missing.values()):
            # この encoding ではヘッダが判定できない → 次の encoding を試す
            continue

        # ここまで来れば、この encoding でヘッダが特定できた
        print(f"[INFO] {p.name}: encoding={enc} で読み込み＆カラム特定OK")

        out = df[[col_date, col_company, col_crop, col_amount]].copy()

        # 型整形
        out[col_amount] = pd.to_numeric(out[col_amount], errors="coerce")

        out = out.rename(
            columns={
                col_date: "c1",
                col_company: "c2",
                col_crop: "c3",
                col_amount: "c4",
            }
        )

        out = out.dropna(subset=["c1", "c3", "c4"])
        return out

    # どの encoding でもヘッダが拾えなかった場合
    raise ValueError(
        f"{p.name}: ヘッダ（収穫日, 企業名, 収穫野菜名, 収穫量）が見つからないか、"
        f"文字コード判定に失敗しました。最後のエラー: {last_err}"
    )


# ------------------------------------------------------------
# １ファイル取り込み
# ------------------------------------------------------------
def import_harvest_csv(path: str) -> None:
    """
    単一の収穫CSVファイルを raw_csv に取り込み、
    harvest_import_log にも記録する。
    """
    ensure_raw_csv_table()
    ensure_harvest_import_log_table()

    p = Path(path)

    if has_been_imported(p):
        print(f"[SKIP] すでに取り込み済み: {p}")
        return

    df = read_harvest_csv(str(p))

    with engine.begin() as conn:
        df.to_sql("raw_csv", conn, if_exists="append", index=False)

    mark_imported(p)
    print(f"[OK] {len(df)} 行を raw_csv に追加しました: {p.name}")


# ------------------------------------------------------------
# メイン処理: inbox/harvest 配下の *.csv を一括取り込み
# ------------------------------------------------------------
if __name__ == "__main__":
    inbox_dir = Path("/home/matsuoka/work-automation/heartful-analytics/data/inbox/harvest")

    if not inbox_dir.exists():
        raise FileNotFoundError(f"inbox/harvest ディレクトリがありません: {inbox_dir}")

    targets = sorted(inbox_dir.glob("*.csv"))

    if not targets:
        raise FileNotFoundError(f"{inbox_dir} に収穫CSVが見つかりません。")

    print(f"{len(targets)} ファイルを処理します。")

    for path in targets:
        print(f"=== {path.name} ===")
        try:
            import_harvest_csv(str(path))
        except Exception as e:
            print(f"[ERROR] {path.name}: {e}")

