# Heartful Agri Compass

収量データ（harvest_fact）をSQLiteに保存し、Streamlitで
- Compass（KPI/ランキング/日別推移）
- Search/List（条件検索・CSVダウンロード）
- CSV Upload（アップロード→クレンジング→重複除外→DB登録）
を行う小規模ダッシュボードです。

## Requirements
- Python 3.12
- pip
- SQLite（Python標準のsqliteでOK）

## Setup
```bash
cd heartful-agri-compass
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt

