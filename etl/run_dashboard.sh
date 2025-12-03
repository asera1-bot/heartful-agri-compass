set -euo pipefail
cd "$(dirname "$0")/.."
source venv/bin/activate 2>/dev/null || true
exec streamlit run apps/farm_dashboard/app.py
