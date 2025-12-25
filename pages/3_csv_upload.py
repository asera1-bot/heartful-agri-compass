def norm_col(s: str) -> str:
    # BOM除去 / 前後空白除去 / 全角スペース除去 / 小文字化（英字）
    s = str(s).replace("\ufeff", "").replace("　", " ").strip()
    return s.lower()

# 正規化したキーで受ける（表記ゆれ吸収）
COL_MAP = {
    # 日付
    "収穫日": "harvest_date",
    "日付": "harvest_date",
    "harvest_date": "harvest_date",
    "date": "harvest_date",

    # 会社
    "企業名": "company",
    "会社名": "company",
    "企業": "company",
    "会社": "company",
    "company": "company",

    # 作物
    "作物名": "crop",
    "収穫野菜名": "crop",
    "品目": "crop",
    "crop": "crop",

    # 収量
    "収穫量（ｇ）": "amount_g",
    "収穫量(ｇ)": "amount_g",
    "収穫量": "amount_g",
    "量": "amount_g",
    "収量(㎏)": "amount_kg",
    "収量(kg)": "amount_kg",
    "amount_g": "amount_g",
    "amount_kg": "amount_kg",
}

# 元の列名 -> 正規化 -> マップ
rename_dict = {}
for c in raw_df.columns:
    key = norm_col(c)
    # COL_MAP は日本語キーが多いので、lower化した日本語でも一致するように一度戻す
    # ここでは「lower化しても日本語は変化しない」前提でOK
    mapped = COL_MAP.get(key) or COL_MAP.get(str(c).replace("\ufeff", "").replace("　"," ").strip())
    if mapped:
        rename_dict[c] = mapped

df = raw_df.rename(columns=rename_dict)

required = {"harvest_date", "company", "crop"}
if not required.issubset(df.columns):
    st.error("必須列が不足しています: " + str(required - set(df.columns)))
    st.write("検出した列:", list(raw_df.columns))
    st.write("正規化後の列:", [norm_col(x) for x in raw_df.columns])
    st.stop()

