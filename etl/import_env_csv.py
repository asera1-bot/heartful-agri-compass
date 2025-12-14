from pathlib import Path
import sys
import re

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# ここでプロジェクトルートを import パスに追加
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "db" / "heartful_dev.db"
inbox_dir = BASE_DIR / "data" / "inbox" / "env"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.db import get_engine, DB_PATH
engine = get_engine()

# ========= テーブル保証系 =========
def ensure_env_raw_table() -> None:
    """env_raw テーブルが無ければ作る（安全に再実行可）。"""
    ddl = """
    CREATE TABLE IF NOT EXISTS env_raw (
      id               INTEGER PRIMARY KEY,
      farm             TEXT NOT NULL,
      ts               TEXT NOT NULL,        -- 'YYYY-MM-DD HH:MM[:SS]'
      air_temp_c       REAL,                 -- CH1: 気温
      rh_percent       REAL,                 -- CH2: 相対湿度(%)
      sand_temp_c      REAL,                 -- CH3: 砂温
      water_content    REAL,                 -- CH4: 含水率
      irradiance_wm2   REAL                  -- CH5: 日射量(W/m2)
    );
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)


def ensure_env_import_log_table() -> None:
    """env_import_log テーブルが無ければ作る。"""
    ddl = """
    CREATE TABLE IF NOT EXISTS env_import_log (
      id          INTEGER PRIMARY KEY,
      path        TEXT NOT NULL UNIQUE,
      imported_at TEXT NOT NULL              -- ISO8601 文字列
    );
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)


def has_been_imported(path: Path) -> bool:
    """指定パスのファイルが既に取り込まれているかを判定する。"""
    sql = "SELECT 1 FROM env_import_log WHERE path = :path LIMIT 1;"
    with engine.begin() as conn:
        row = conn.execute(text(sql), {"path": str(path)}).fetchone()
    return row is not None


def mark_imported(path: Path) -> None:
    """指定パスをインポート済みとしてログに記録する。"""
    sql = """
    INSERT OR IGNORE INTO env_import_log(path, imported_at)
    VALUES(:path, datetime('now'));
    """
    with engine.begin() as conn:
        # ★ ここは dict なので {"path": str(path)} が正しい
        conn.execute(text(sql), {"path": str(path)})


# ========= GL240 CSV → env_raw DataFrame =========
def read_gl240_csv(path: str, farm: str) -> pd.DataFrame:
    """
    GL240 の CSV を読み込み、env_raw 形式の DataFrame を返す。

    - 文字コードを自動判別（utf-8-sig → utf-8 → utf-16le → cp932)
    - 「CH1, CH2, …」を含む行をヘッダー行として採用
    - 次行の No./単位行は読み込まれても後段で除去
    """
    p = Path(path)

    # 1) エンコーディングとヘッダー行（CH行）を検出
    enc_candidates = ["utf-8-sig", "utf-8", "utf-16le", "cp932"]
    chosen_enc = None
    ch_header_row = None

    for enc in enc_candidates:
        try:
            with p.open(encoding=enc, errors="strict") as f:
                for i, line in enumerate(f):
                    # タブ・カンマをすべてカンマに正規化
                    s = re.sub(r"[\t,]+", ",", line.strip(), flags=re.ASCII)
                    if (
                        re.search(r"\bCH\s*0*1\b", s, flags=re.IGNORECASE)
                        and re.search(r"\bCH\s*0*2\b", s, flags=re.IGNORECASE)
                    ):
                        chosen_enc = enc
                        ch_header_row = i
                        break
            if chosen_enc is not None:
                break
        except UnicodeDecodeError:
            continue

    if chosen_enc is None or ch_header_row is None:
        raise ValueError(
            "ヘッダー行（CH1, CH2 を含む行）が見つからないか、文字コード判定に失敗しました。"
        )

    # 2) 読み込み（カンマ/タブ両対応）
    df = pd.read_csv(
        p,
        encoding=chosen_enc,
        header=ch_header_row,
        engine="python",
        sep=r"[,\t]+",
    )

    # 3) 列名を正規化（空白・全角空白除去、 "CH 1"→"CH1")
    df.columns = (
        df.columns.astype(str)
        .str.replace(r"\s+", "", regex=True)
        .str.replace("　", "")   # 全角スペースも一応消しておく
    )

    # 4) 時刻列の特定
    col_time = None

    # 4-1) よくある英語・日本語パターンで探す
    for c in df.columns:
        lc = c.lower()
        if lc in ("time", "時刻", "datetime", "日付時刻"):
            col_time = c
            break

    # 4-2) "time" を含む列名を探す (Time, LogTime など)
    if col_time is None:
        for c in df.columns:
            if "time" in c.lower():
                col_time = c
                break

    # 4-3) 日本語パターン："日付" または "日時" または "時間" を含むもの
    if col_time is None:
        for c in df.columns:
            if ("日付" in c) or ("日時" in c) or ("時間" in c):
                col_time = c
                break

    # 4-4) それでも見つからない場合は「2列目を時刻扱い」にフォールバック
    if col_time is None and len(df.columns) >= 2:
        col_time = df.columns[1]

    if col_time is None:
        raise ValueError(f"時刻列が特定できません。列名:{list(df.columns)}")

    # 5) CH1 ~ CH5 の列名を柔軟に特定
    def find_ch(colnames, n: int):
        pat1 = re.compile(rf"^ch[_\-]*0*{n}$", re.IGNORECASE)
        pat2 = re.compile(rf"^ch[_\-]*0*{n}\b", re.IGNORECASE)
        for name in colnames:
            if pat1.match(name):
                return name
        for name in colnames:
            if pat2.match(name):
                return name
        return None

    ch1 = find_ch(df.columns, 1)
    ch2 = find_ch(df.columns, 2)
    ch3 = find_ch(df.columns, 3)
    ch4 = find_ch(df.columns, 4)
    ch5 = find_ch(df.columns, 5)

    required = {"CH1": ch1, "CH2": ch2, "CH3": ch3, "CH4": ch4, "CH5": ch5}
    if any(v is None for v in required.values()):
        raise ValueError(f"CH1~CH5 の列が特定できません: {required}")

    # 6) 必要列のみ抽出し、型を整える（単位行は NaT/NaN になり後で除去）
    df = df[[col_time, ch1, ch2, ch3, ch4, ch5]].copy()
    df[col_time] = pd.to_datetime(df[col_time], errors="coerce")
    for c in [ch1, ch2, ch3, ch4, ch5]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # 7) 単位行などを除去
    df = df.dropna(subset=[col_time])

    # 8) 列名を標準化し、farm を付与
    df = df.rename(
        columns={
            col_time: "ts",
            ch1: "air_temp_c",
            ch2: "rh_percent",
            ch3: "sand_temp_c",
            ch4: "water_content",
            ch5: "irradiance_wm2",
        }
    )
    df["farm"] = farm

    # 9) 列順を整える
    df = df[
        [
            "farm",
            "ts",
            "air_temp_c",
            "rh_percent",
            "sand_temp_c",
            "water_content",
            "irradiance_wm2",
        ]
    ]
    return df


# ========= CSV → env_raw 取り込み =========
def import_env_csv(path: str, farm: str) -> None:
    """CSV を env_raw に取り込み、ログも記録する。"""
    ensure_env_raw_table()
    ensure_env_import_log_table()

    p = Path(path)

    if has_been_imported(p):
        print(f"[SKIP] すでに取り込み済み: {p}")
        return

    df = read_gl240_csv(str(p), farm)

    with engine.begin() as conn:
        df.to_sql("env_raw", conn, if_exists="append", index=False)

    mark_imported(p)
    print(f"[OK] {len(df)} 行を env_raw に追加しました: {p.name}")


# ========= VPD + 集計 / VIEW 再構築 =========
def add_vpd_column(
    df: pd.DataFrame,
    temp_col: str = "mean_temp",
    rh_col: str = "mean_humidity",
    vpd_col: str = "vpd_kpa",
) -> pd.DataFrame:
    """
    df に VPD(kPa) 列を追加して返す。
    必須: temp_col(℃), rh_col(相対湿度%)
    """
    T = df[temp_col].astype(float)
    RH = df[rh_col].astype(float)

    # 飽和水蒸気圧(kPa) 近似
    es = 0.6108 * np.exp((17.27 * T) / (T + 237.3))
    vpd = es * (1.0 - RH / 100.0)

    df[vpd_col] = vpd
    return df


def rebuild_env_daily_and_views() -> None:
    """
    env_raw から env_daily を再作成し、
    env_monthly / v_harvest_env の VIEW を張り直す。
    """
    print("[INFO] env_daily / env_monthly / v_harvest_env を再構築する。")

    with engine.begin() as conn:
        # env_raw -> pandas
        df_raw = pd.read_sql(
            """
            SELECT farm, ts, air_temp_c, rh_percent, sand_temp_c, water_content, irradiance_wm2
            FROM env_raw;
            """,
            conn,
            parse_dates=["ts"],
        )

    if df_raw.empty:
        print("[WARN] env_raw にデータがありません。集計をスキップします。")
        return

    # 日付列を作成
    df_raw["date"] = df_raw["ts"].dt.date

    # 日単位集計
    df_daily = (
        df_raw.groupby(["farm", "date"], as_index=False)
        .agg(
            mean_temp=("air_temp_c", "mean"),
            mean_humidity=("rh_percent", "mean"),
            mean_sand_temp=("sand_temp_c", "mean"),
            mean_water_content=("water_content", "mean"),
            mean_irradiance=("irradiance_wm2", "mean"),
        )
    )

    # VPD 列を追加
    df_daily = add_vpd_column(
        df_daily,
        temp_col="mean_temp",
        rh_col="mean_humidity",
        vpd_col="vpd_kpa",
    )

    # env_daily テーブルとして保存（毎回作り直し）
    with engine.begin() as conn:
        # まず env_daily が view か table かを確認してから drop
        row = conn.exec_driver_sql(
            "SELECT type FROM sqlite_master WHERE name='env_daily';"
        ).fetchone()

        if row:
            obj_type = row[0]
            if obj_type == "view":
                conn.exec_driver_sql("DROP VIEW env_daily;")
            elif obj_type == "table":
                conn.exec_driver_sql("DROP TABLE env_daily;")

        # 改めて「テーブル」として作成
        df_daily.to_sql("env_daily", conn, if_exists="replace", index=False)

        # env_monthly VIEW を再作成
        conn.exec_driver_sql("DROP VIEW IF EXISTS env_monthly;")
        conn.exec_driver_sql(
            """
            CREATE VIEW env_monthly AS
            SELECT
                farm,
                strftime('%Y-%m', date) AS month,
                AVG(mean_temp)          AS mean_temp,
                AVG(mean_humidity)      AS mean_humidity,
                AVG(vpd_kpa)            AS mean_vpd_kpa,
                AVG(mean_sand_temp)     AS mean_sand_temp,
                AVG(mean_water_content) AS mean_water_content,
                AVG(mean_irradiance)    AS mean_irradiance
            FROM env_daily
            GROUP BY farm, month;
            """
        )

        # v_harvest_env VIEW
        conn.exec_driver_sql("DROP VIEW IF EXISTS v_harvest_env;")
        conn.exec_driver_sql(
            """
            CREATE VIEW v_harvest_env AS
            SELECT
                h.farm,
                h.month,
                h.total_kg AS mean_kg,
                e.mean_temp,
                e.mean_humidity AS mean_humid,
                e.mean_vpd_kpa,
                e.mean_sand_temp,
                e.mean_water_content,
                e.mean_irradiance
            FROM harvest_monthly h
            LEFT JOIN env_monthly e
              ON h.farm  = e.farm
             AND h.month = e.month;
            """
        )

    print("[OK] env_daily / env_monthly / v_harvest_env の再構築が完了しました。")


# ========= メイン処理 =========
if __name__ == "__main__":
    if not inbox_dir.exists():
        raise FileNotFoundError(f"inbox ディレクトリがありません: {inbox_dir}")

    # 1) Converted ファイル（優先して扱いたいもの）
    converted_files = sorted(inbox_dir.glob("*_Converted.csv"))

    # 2) 通常の .csv（Converted 以外）
    raw_files = sorted(
        p for p in inbox_dir.glob("*.csv") if not p.name.endswith("_Converted.csv")
    )

    targets = converted_files + raw_files

    if not targets:
        raise FileNotFoundError(f"{inbox_dir} に対象となる CSV が見つかりません。")

    print(f"{len(targets)} ファイルを取り込みます。")

    for path in targets:
        print(f"=== {path.name} ===")
        try:
            import_env_csv(str(path), "愛川C1")
        except Exception as e:
            print(f"[ERROR] {path.name}: {e}")

    # 取り込み後に集計と VIEW 再構築
    rebuild_env_daily_and_views()

