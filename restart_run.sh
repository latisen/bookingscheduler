#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

cd "$PROJECT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtuell miljö saknas. Kör ./first_run.sh först."
  exit 1
fi

echo "[1/4] Aktiverar virtuell miljö..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[2/4] Säkerställer beroenden efter uppdatering..."
python -m pip install -r requirements.txt

echo "[3/4] Stoppar eventuell tidigare app på port 5000..."
if lsof -ti tcp:5000 >/dev/null 2>&1; then
  lsof -ti tcp:5000 | xargs kill
fi

echo "[4/4] Startar Flask-appen igen..."
python run.py
