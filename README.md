# Heartful Agri Compass

収量データ（CSV）をSQLiteに登録し、Streamlitで
- Compass（KPI/ランキング/推移）
- Search/List（検索・一覧・CSVダウンロード）
- CSV Upload（ブラウザからアップロードしてDB反映）
を行うミニアプリです。

---

---
# directory

.
├── .git
│   ├── COMMIT_EDITMSG
│   ├── FETCH_HEAD
│   ├── HEAD
│   ├── ORIG_HEAD
│   ├── branches
│   ├── config
│   ├── description
│   ├── hooks
│   ├── index
│   ├── info
│   ├── logs
│   ├── objects
│   ├── packed-refs
│   └── refs
├── .gitignore
├── .streamlit
│   └── secrets.toml
├── ARCHITECTURE.md
├── Home.py
├── README.md
├── app
│   ├── __init__.py
│   ├── __pycache__
│   ├── common
│   ├── core
│   ├── farm_dashboard
│   └── legacy_pages
├── data
│   ├── archive
│   ├── db
│   └── inbox
├── db
│   ├── heartful_dev.db
│   └── heartful_real.db
├── etl
│   ├── __pycache__
│   ├── backup_sqlite.sh
│   ├── import_env_csv.py
│   ├── import_harvest_csv.py
│   ├── refresh_mv.sh
│   └── run_dashboard.sh
├── main.py
├── pages
│   ├── 1_Compass.py
│   ├── 2_Search_list.py
│   ├── 3_csv_upload.py
│   └── __init__.py
├── requirements.txt
├── sample
│   └── harvest_sample.csv
└── venv
    ├── bin
    ├── etc
    ├── include
    ├── lib
    ├── lib64 -> lib
    ├── pyvenv.cfg
    └── share
---

# Demo
- App: https://heartful-agri-compass-vz7n5dmgakbpyfkgkvnr2h.streamlit.app/
- Custom Domain: https://heartfulagri.com （Cloudflare Redirect → Streamlit）

---

# Login
※ ログインID/パスワードは Streamlit secrets で管理しています。

- ローカル: `.streamlit/secrets.toml` に設定
- Streamlit Cloud: Secrets に設定

---

# Futures

- ログイン機能（簡易）
- 収量CSVの取り込み
  - 文字コードフォールバック（utf-8-sig / cp932）
  - 収量の g / kg 表記を吸収して kg に正規化
  - 日付の正規化（YYYY/MM/DD, YYYY-MM-DD, Excelシリアル）
  - 既存データとの重複チェック（同一行は追加しない）
- Search/List
  - 期間・企業・作物でフィルタ
  - ページネーション
  - フィルタ結果のCSVダウンロード

---

# Setup

1. 仮想環境の作成

```bash
python3 -m venv venv
source venv/bin/activate

依存関係インストール
pip install -r requirements.txt

※　もしもpipが壊れている場合
python3 -m pip install -r requirements.txt

---

# Secrets（ローカル）
.streamlit/secrets.toml　を作成し、usersを設定してください（例）
[users]
admin = "admin_password"
teppei = "teppei_password"

起動
python -m streamlit run Home.py

---

# Sample CSV
動作確認用のCSVは sample/harvest_sample.csv を参照してください。
