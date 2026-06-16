#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# run_local.sh - Run the Thoughts Dashboard Flask app locally
# Connects to the PostgreSQL instance already running in the cluster.
# ---------------------------------------------------------------------------

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

# ---------- Database connection (override via env vars if needed) -----------
export DB_HOST="${DB_HOST:-postgresql.thoughts-app.svc.cluster.local}"
export DB_NAME="${DB_NAME:-thoughts}"
export DB_USER="${DB_USER:-thoughts}"
export DB_PASSWORD="${DB_PASSWORD:-thoughts123}"
export DB_PORT="${DB_PORT:-5432}"

# ---------- Flask / app settings -------------------------------------------
export PORT="${PORT:-8080}"
export FLASK_ENV="${FLASK_ENV:-development}"

# ---------------------------------------------------------------------------
echo "=== Thoughts Dashboard - Local Runner ==="
echo "DB host   : $DB_HOST:$DB_PORT/$DB_NAME"
echo "App port  : $PORT"
echo ""

# ---------- Activate virtual environment -----------------------------------
if [ ! -f "$VENV_DIR/bin/activate" ]; then
  echo "[setup] Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# ---------- Install / sync dependencies ------------------------------------
echo "[setup] Installing dependencies from requirements.txt..."
pip install --quiet -r "$PROJECT_DIR/requirements.txt"

# ---------- Start the app --------------------------------------------------
echo "[start] Starting Flask app on http://0.0.0.0:$PORT ..."
echo ""
python "$PROJECT_DIR/app.py"
