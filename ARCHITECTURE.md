# Heartful Agri Compass - Architecture

# 1. 概要
Heartful Agri Compass は、収量CSVを登録・蓄積し、
検索・可視化（Compass / Search List)を行うStremlit 制webアプリです。

現場での運用（CSV登録　→　即時確認）と
クラウド環境（Streamlit Cloud) での再現性を重視した構成としています。

# 2. 全体構成
heartful-agri-compass/
├── .gitignore
├── ARCHITECTURE.md
├── Home.py
├── README.md
├── main.py
├── requirements.txt
├── app/
│   ├── common/
│   ├── core/
│   │   ├── auth.py
│   │   └── db.py
│   ├── farm_dashboard/
│   └── legacy_pages/
├── pages/
│   ├── 1_Compass.py
│   ├── 2_Search_list.py
│   └── 3_csv_upload.py
├── etl/
│   ├── import_harvest_csv.py
│   ├── import_env_csv.py
│   ├── backup_sqlite.sh
│   ├── refresh_mv.sh
│   └── run_dashboard.sh
├── data/
│   ├── inbox/
│   └── archive/
├── db/
│   ├── heartful_dev.db
│   └── heartful_real.db
└── sample/
    └── harvest_sample.csv

# 3. 技術スタック
- Feontend / UI:Stramlit
- Backend / Logic:Python 3.x,Pandas,SQLAlchemy
- Database:SQLite
- Infra:Streamlit Cloud

# 4. データフロー
4.1 CSV Upload
1. CSVファイルをアップロード
2. 列名正規化・型変換・クレンジング
3. 重複判定（INSERT OR IGNORE)
4. SQLite (harvest_fact)に登録

4.2 Sreach / List
1. DBからデータ取得
2. 期間・企業・作物フィルタ
3. 一覧表示・CSVダウンロード

4.3 Compass
1. DBからデータ取得
2. KPI・ランキング・時系列可視化

# 5. DB設計

harvest_fact

| column        | type       | note        |
|---------------|------------|-------------|
| id            | INTEGER    | PK          |
| harvest_date  | TEXT       | YYYY-MM-DD  |
| company       | TEXT       | 企業名      |
| crop          | TEXT       | 作物名      |
| amount_kg     | REAL       | 収量（kg）  |

- 重複判定
  `(harvest_date, company, crop,amount_kg)` を同一とみなす
- INSERT OR IGNORE により二重登録を防止

6. 設計の判断

相対パス採用
- ローカル　/　クラウド共通で動作させるため
- 個人名・環境情報の公開リスク回避

マイグレーション未導入
- 現時点ではテーブル構造が単純なため
- 今後、テーブル増加時に Alembic 等を導入予定

ファイル番号の違い
- Streramlit pages の表示制御のため一部で使用
- 今後は pages 設計の整理で廃止予定

7. 展望
- マイグレーション導入(Alembic)
- DBインデックス設計
- 認可(role)拡張
