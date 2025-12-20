import io
import re
from datetime import datetime, timedelta
from etl.import_harvest_csv import upsert_raw_to_harvest_fact

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_engine, DB_PATH
from app.core.auth import require_login

require_login()

st.markdown("### CSV アップロード")
st.caption("収量データCSVをアップロードして、harvest_fact に反映します。")
st.write(f"現在のDBパス: `{DB_PATH}`")

# ---------- helpers ----------
ZEN_NUM = str.maketrans("０１２３４５６７８９．，", "0123456789.,")
EXCEL_EPOCH = datetime(1899, 12, 30)

def parse_amount_to_kg(val) -> float | None:
    """'1234', '1,234', '12.3kg', '123g' 等を kg(float) にする"""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    s = s.translate(ZEN_NUM).replace(",", "")
    s_low = s.lower()

    m = re.search(r"[-+]?\d*\.?\d+", s_low)
    if not m:
        return None
    x = float(m.group())

    if "kg" in s_low:
        return x
    return x / 1000.0

def parse_harvest_date(val) -> str | None:
    """
    受ける例:
    - 2025/8/18, 2025/08/18, 2025-08-18
    - Excelシリアル (30000~60000程度)
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    # Excelシリアル
    if s.isdigit():
        n = int(s)
        if 30000 <= n <= 60000:
            return (EXCEL_EPOCH + timedelta(days=n)).date().isoformat()

    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass

    dt = pd.to_datetime(s, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.date().isoformat()

def read_csv_bytes(bytes_data: bytes) -> tuple[pd.DataFrame, str]:
    candidates = [
        ("utf-8-sig", dict(encoding="utf-8-sig", sep=",")),
        ("cp932",     dict(encoding="cp932", sep=",")),
        ("cp932_auto", dict(encoding="cp932", sep=None, engine="python")),
    ]
    last_errs = []
    for label, params in candidates:
        try:
            buf = io.BytesIO(bytes_data)
            df = pd.read_csv(buf, **params)
            return df, label
        except Exception as e:
            last_errs.append(f"{label}: {e}")
    raise RuntimeError("CSV decode failed:\n" + "\n".join(last_errs))

def ensure_harvest_fact_table():
    ddl = """
    CREATE TABLE IF NOT EXISTS harvest_fact (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        harvest_date TEXT NOT NULL,
        company      TEXT NOT NULL,
        crop         TEXT NOT NULL,
        amount_kg    REAL NOT NULL
    );
    """
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)

def normalize_amount_for_compare(x):
    """
    重複判定用: amount_kg を少数3桁に丸めて比較する
    - DBから文字列で来てもOK
    ‐ None/Nanは None を返す
    """
    if x is None:
        return None
    try:
        # 文字列→数値へ("1.23"　等もOK)
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, 3)



# ---------- upload ----------
uploaded = st.file_uploader("収量CSVのファイルを選択してください", type=["csv"])
if uploaded is None:
    st.stop()

bytes_data = uploaded.getvalue()

try:
    raw_df, used_label = read_csv_bytes(bytes_data)
except Exception as e:
    st.error("CSVの読み込みに失敗しました。")
    st.exception(e)
    st.stop()

st.success(f"CSVを読み込みました (mode={used_label})")

# ---------- normalize columns ----------
col_map = {
    "収穫日": "harvest_date",
    "日付": "harvest_date",
    "企業名": "company",
    "会社名": "company",
    "作物名": "crop",
    "収穫野菜名": "crop",
    "品目": "crop",
    "収穫量（ｇ）": "amount_g",
    "収穫量(ｇ)": "amount_g",
    "収穫量": "amount_g",
    "量": "amount_g",
    "収量(㎏)": "amount_kg",
    "収量(kg)": "amount_kg",
}

df = raw_df.rename(columns={c: col_map.get(str(c).strip(), str(c).strip()) for c in raw_df.columns})

required_any = {"harvest_date", "company", "crop"}
if not required_any.issubset(df.columns):
    st.error(f"必須列が足りません。必要: {sorted(required_any)} / 現在: {list(df.columns)}")
    st.stop()

# amount_kg を作る
if "amount_kg" in df.columns:
    df["amount_kg"] = df["amount_kg"].apply(normalize_amount_for_compare)
elif "amount_g" in df.columns:
    df["amount_kg"] = df["amount_g"].apply(normalize_amount_for_compare)
else:
    st.error("収量列が見つかりません（amount_g / amount_kg 相当が必要）。")
    st.stop()

# 日付/文字列を正規化
df["harvest_date"] = df["harvest_date"].apply(parse_harvest_date)
df["company"] = df["company"].astype(str).str.strip()
df["crop"] = df["crop"].astype(str).str.strip()

# ---------- cleansing ----------
before = len(df)

df = df.dropna(subset=["harvest_date", "company", "crop", "amount_kg"])
df = df[(df["company"] != "") & (df["crop"] != "")]

# 未来日除外
today = pd.Timestamp.today().date()
future_mask = pd.to_datetime(df["harvest_date"], errors="coerce").dt.date > today
future_rows = df[future_mask].copy()
df = df[~future_mask]

# マイナス除外
neg_mask = df["amount_kg"] < 0
neg_rows = df[neg_mask].copy()
df = df[~neg_mask]

# 重複判定用に amount_kg を丸める（※DB保存値も同じ丸めで揃えると最強）
df["amount_kg"] = df["amount_kg"].apply(lambda x: None if x is None else normalize_amount_for_compare(x))

after = len(df)
dropped = before - after

st.info(
    f"""**クレンジング結果**
- 元データ: {before} 行
- 有効: {after} 行
- 欠損/不正除外: {dropped} 行
- 未来日除外: {len(future_rows)} 行
- マイナス除外: {len(neg_rows)} 行
"""
)

if not future_rows.empty:
    with st.expander("除外された未来日の行（先頭10件）"):
        st.dataframe(future_rows.head(10), width="stretch")

if not neg_rows.empty:
    with st.expander("除外されたマイナス収量の行（先頭10件）"):
        st.dataframe(neg_rows.head(10), width="stretch")

if df.empty:
    st.error("有効なレコードがありません。CSVの内容を確認してください。")
    st.stop()

st.markdown("### プレビュー（クレンジング後）")
st.dataframe(df.head(20), width="stretch")

# ---------- duplicate check ----------
ensure_harvest_fact_table()

merge_cols = ["harvest_date", "company", "crop", "amount_kg"]
df = df[merge_cols].copy()

engine = get_engine()
with st.spinner("DB 既存データとの重複をチェック中..."):
    try:
        with engine.connect() as conn:
            existing = pd.read_sql_query(
                "SELECT harvest_date, company, crop, amount_kg FROM harvest_fact",
                conn,
            )
            # 既存側も丸めて比較の軸を揃える（浮動小数誤差対策）
            existing["amount_kg"] = existing["amount_kg"].apply(normalize_amount_for_compare)
            existing = existing.dropna(subset=["amount_kg"])
    except SQLAlchemyError:
        existing = pd.DataFrame(columns=merge_cols)

if existing.empty:
    df_new = df.copy()
    df_dup = pd.DataFrame(columns=merge_cols)
else:
    merged = df.merge(existing[merge_cols], how="left", on=merge_cols, indicator=True)
    df_new = merged[merged["_merge"] == "left_only"][merge_cols].copy()
    df_dup = merged[merged["_merge"] == "both"][merge_cols].copy()

st.subheader("重複チェック結果")
st.write(f"新規データ: **{len(df_new)} 件**")
st.write(f"既存と重複: **{len(df_dup)} 件**")

if len(df_dup) > 0:
    st.warning("以下は DB に既に存在し、今回のアップロードでは追加されません（先頭10件）。")
    st.dataframe(df_dup.head(10), width="stretch")

if len(df_new) == 0:
    st.info("追加できる新規データがありません。")
    st.stop()

st.markdown("### 🔵 新規データ（登録予定）")
st.dataframe(df_new.head(20), width="stretch")

# ---------- insert ----------
if st.button("この内容で harvest_fact に登録する", type="primary"):
    with st.spinner("DBに登録中…"):
        try:
            df_raw = df_new.rename(columns={
                "harvest_date": "c1",
                "company": "c2",
                "crop": "c3",
                "amount_kg": "c4",
            }).copy()

            df_raw["source_file"] = "csv_upload"

            with engine.begin() as conn:
                df_raw.to_sql(
                    "raw_csv",
                    conn,
                    if_exists="append",
                    index=False
                )

                inserted = upsert_raw_to_harvest_fact()

                st.success(
                    f"harvest_factへ反映されました。"
                    f"（新規候補={len(df_new)}行 / 実際に反映={inserted}行)"
                )
        except SQLAlchemyError as e:
            st.error("データベースへの登録に失敗しました。")
            st.code(str(DB_PATH), language="bash")
            st.exception(e)
            st.stop()

    st.info("SearchList / Compass を再読み込みすると反映されます。")
