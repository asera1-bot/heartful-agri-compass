from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_DIR = ROOT_DIR / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "heartful_dev.db"


# ブランド系farm
FARM_BRAND_AIKAWA_FRUIT_ICHIGO      = "Aikawa-FRUIT-Ichigo"
FARM_BRAND_AIKAWA_FRUIT_MINITOMATO  = "Aikawa-FRUIT-MiniTomato"
FARM_BRAND_AIKAWA_FRUIT_ISLANDCHILI = "Aikawa-FRUIT-IslandChili"
FARM_BRAND_AIKAWA_LEAF_BABYLEAF     = "Aikawa-LEAF-BabyLeaf"
FARM_BRAND_AIKAWA_LEAF_KALE         = "Aikawa-LEAF-Kale"

# 実験棟イチゴ　段差
FARM_JIKKEN_ICHIGO_UW    = "Jikken-Ichigo-Ue"
FAMR_JIKKEN_ICHIGO_BED   = "Jikken-Ichigo-Bed"
FARM_JIKKEN_ICHIGO_SHITA = "Jikken-Ichigo-Shita"
