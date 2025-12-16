# Heartful Agri Compass

収量データ（CSV）をSQLiteに登録し、Streamlitで
- Compass（KPI/ランキング/推移）
- Search/List（検索・一覧・CSVダウンロード）
- CSV Upload（ブラウザからアップロードしてDB反映）
を行うミニアプリです。

---

## Features

- ログイン機能（簡易）
- SQLite（ローカルDB）
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

## Directory

.
├── app
│ ├── main.py
│ ├── core
│ │ ├── auth.py
│ │ └── db.py
│ └── pages
│ ├── 1_Compass.py
│ ├── 2_SearchList.py
│ └── 3_CSV_Upload.py
├── etl
│ └── import_harvest_csv.py
├── data
│ └── inbox
│ └── harvest (ETL取り込み用CSV置き場)
├── db
│ └── heartful_dev.db (ローカルDB / git管理しない)
├── requirements.txt
└── venv/ (git管理しない)


---

## Requirements

- Python 3.12（または 3.11 でも可）
- Linux / WSL2 / Ubuntu想定

---

## Setup

### 1) 仮想環境の作成

```bash
python3 -m venv venv
source venv/bin/activate

依存関係インストール
pip install -r requirements.txt


（もし pip が無い/壊れてる場合）

python3 -m pip install -r requirements.txt

Run (Streamlit)

基本はこれでOK：

./venv/bin/python -m streamlit run app/main.pystreamlit run app/main.py が動かない環境では、上の python -m 方式が確実です
（PATHがvenvを見ていない/別pythonを見ているケースがあるため）

起動後：

Local URL: http://localhost:8501
