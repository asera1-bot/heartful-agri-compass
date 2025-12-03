set -euo pipefail
cd "$(dirname"$0")/.."
mkdir -p backups
TS=$(date +%Y%m%d_%H%M)
cp data/db/harvests_real.db backups/harvests_real_${TS}.db
