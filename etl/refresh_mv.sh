set -euo pipefail
cd "$(dirname"$0")/.."
python3 jobs/update_mv_farm_month_totals.py --db data/db/harvests_real.db --mode full
