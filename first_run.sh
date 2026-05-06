#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

cd "$PROJECT_DIR"

echo "[1/5] Skapar virtuell miljö om den saknas..."
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

echo "[2/5] Aktiverar virtuell miljö..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[3/5] Installerar beroenden..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "[4/5] Initierar datafiler från seed..."
mkdir -p data
for seed_file in data/seed/seed_*.json; do
  [[ -e "$seed_file" ]] || continue
  target_file="data/$(basename "$seed_file" | sed 's/^seed_//')"
  cp "$seed_file" "$target_file"
done

echo "[5/5] Startar Flask-appen..."
python run.py
