import io
from datetime import datetime

import pandas as pd
import streamlit as st

from core.db import get_engine, DB_PATH
from core.auth import require_login

# ログイン必須
require_login()

st.markdown("### CSV アップロード")
st.caption("収量データのCSVをアップロードして、harvest_factテーブルに反映します。")

st.write(f"現在のDBパス: `{DB_PATH}`")

# CSV アップロード
uploaded = st.file_uploader("収量CSVのファイルを選択してください", type=["csv"])

if uploaded is None:
    st.stop()

# 一度だけ生バイトを取り出して、以後はこの bytes_data から読み込む
bytes_data = uploaded.getvalue()

df = None
used_label = None
errors = []

candidates = [
    ("utf-8-sig", dict(encoding="utf-8-sig", sep=",")),
    ("cp932",     dict(encoding="cp932", sep=",")),
    ("cp932_auto", dict(encoding="cp932", sep=None, engine="python")),
]

for label, params in candidates:
    try:
        buffer = io.BytesIO(bytes_data)
        df = pd.read_csv(buffer, **params)
        used_label = label
        break
    except Exception as e:
        errors.append(f"{label}: {e}")

if df is None:
    st.error("CSVの読み込みに失敗しました。 \n" + "\n".join(errors))
    st.stop()

st.success(f"CSVを読み込みました(mode={used_label})")

# ここに日本語ヘッダー→内部スキーマ+g→㎏変換を入れる
col_map = {
    "収穫日": "harvest_date",
    "企業名": "company",
    "作物名": "crop",
    "収穫野菜名": "crop",
    "収穫量（ｇ）": "amount_g",
    "収穫量(ｇ)": "amount_g",
    "収量(㎏)": "amount_kg",
}

df = df.rename(columns=col_map)

# g→㎏変換(amount_g があって amount_kg がまだない場合)
if "amount_g" in df.columns and "amount_kg" not in df.columns:
    df["amount_kg"] = pd.to_numeric(df["amount_g"], errors="coerce") / 1000

# 必須カラムチェック
required_cols = {"harvest_date", "company", "crop", "amount_kg"}
missing = required_cols - set(df.columns)

if missing:
    st.error(f"必須カラムが足りません: {', '.join(sorted(missing))}")
    st.stop()

# 必須カラムだけに絞る（余計な列は無視）
df = df[list(required_cols)]

# 型変換
df["harvest_date"] = pd.to_datetime(df["harvest_date"], errors="coerce")
df["amount_kg"] = pd.to_numeric(df["amount_kg"], errors="coerce")

before_rows = len(df)
df = df.dropna(subset=["harvest_date", "company", "crop", "amount_kg"])
after_rows = len(df)
dropped = before_rows - after_rows

if dropped > 0:
    st.warning(f"日付/企業名/作物/収量に欠損がある {dropped} 行を除外しました。")

# 未来日（今日より）を除外
today = pd.Timestamp.today().normalize()
future_mask = df["harvest_date"] > today
future_rows = df[future_mask]

if not future_rows.empty:
    st.warning(f"未来日({today.date()} より後)のデータ {len(future_rows)}行を除外しました。")
    with st.expander("除外された未来日の行を表示"):
        st.dataframe(future_rows, width="stretch")
    df = df[~future_mask]

# マイナス収量を除外
neg_mask = df["amount_kg"] < 0
neg_rows = df[neg_mask]

if not neg_rows.empty:
    st.warning(f"収量がマイナスのデータ {len(neg_rows)} 行を除外しました。")
    with st.expander("除外されたマイナス収量の行を表示"):
        st.dataframe(neg_rows, width="stretch")
    df = df[~neg_mask]

if df.empty:
    st.error("有効なレコードがありません。CSVの内容を確認してください。")
    st.stop()

# DB 側は TEXT で受ける想定（YYYY-MM-DD文字列）
df["harvest_date"] = df["harvest_date"].dt.strftime("%Y-%m-%d")

st.markdown("### 🟡 重複データ（DBに既に存在")
st.write(f"クレンジング後のレコード数: {len(df)}")
st.dataframe(df.head(10), width="stretch")

# 既存データとの重複チェック　＆　差分抽出
engine = get_engine()

with st.spinner("棄損データとの重複をチェックします。"):
    try:
        with engine.connect() as conn:
               existing = pd.read_sql_query(
                   """
                   select harvest_date, company, crop, amount_kg
                   from harvest_fact
                   """,
                   conn,
                )
    except Exception:
        # テーブルがまだ無い等の場合は「既存なし」として扱う
        existing = pd.DataFrame(columns=["harvest_date", "company", "crop", "amount_kg"])

merge_cols = ["harvest_date", "company", "crop", "amount_kg"]

if existing.empty:
    # 既存が無い場合は全件が新規
    df_new = df.copy()
    df_dup = pd.DataFrame(columns=merge_cols)
else:
    df_merged = df.merge(existing, how="left", on=merge_cols, indicator=True)
    df_new = df_merged[df_merged["_merge"] == "left_only"][merge_cols].copy()
    df_dup = df_merged[df_merged["_merge"] == "both"][merge_cols].copy()

num_new = len(df_new)
num_dup = len(df_dup)

st.subheader("重複チェック結果")
st.write(f"新規データ: **{num_new}件**")
st.write(f"既存と重複していたデータ: **{num_dup}件**")

if num_dup > 0:
    st.warning("以下は DB に既に存在し、今回のアップロードでは追加されません。")
    st.dataframe(df_dup.head(10), width="stretch")

if num_new == 0:
    st.info(f"""
    **クレンジング結果**
    - 有効レコード数: {len(df)}
    - 欠損除外: {dropped} 行
    - 未来日除外: {len(future_rows)} 行
    - マイナス除外: {len(neg_rows)} 行
    """)
    st.stop()

st.markdown("### 🔵 新規データ（登録予定）")
st.dataframe(df_new.head(20), width="stretch")

# DB へ書き込み
if st.button("この内容で harvest_fact に登録する", type="primary"):
    with st.spinner("データベースに登録しています。"):
        try:
            with engine.begin() as conn:
                # id は DB 側の AUTOINCREMENT に任せる想定
                df_new.to_sql("harvest_fact", conn, if_exists="append", index=False)
        except DQLAlchemyError as e:
            st.error("データベースへの登録に失敗しました。")
            st.code(str(DB_PATH), language="bash")
            st.exception(e)
            st.stop()

st.success(f"harvest_fact に **{len(df_new)} 行** を追加しました。")
st.info("Compass 画面を再読み込みすると、指標とグラフに反映されます。")
