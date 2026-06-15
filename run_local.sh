#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_local.sh  –  Start the Thoughts Dashboard against the live database
#
# Usage:
#   bash run_local.sh          # default port 8080
#   PORT=9090 bash run_local.sh
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8080}"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()   { echo -e "${GREEN}[ OK ]${NC}  $*"; }
fail() { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

echo ""
echo "======================================================"
echo "  Thoughts Dashboard – Local Runner"
echo "======================================================"
echo ""

# ── 1. Python ────────────────────────────────────────────────────────────────
command -v python3 &>/dev/null || fail "python3 not found. Install Python 3.8+."
info "$(python3 --version)"

# ── 2. pip bootstrap (safe no-op if already present) ────────────────────────
if ! python3 -m pip --version &>/dev/null; then
  info "pip not found – bootstrapping via ensurepip..."
  python3 -m ensurepip
fi

# ── 3. Install dependencies ──────────────────────────────────────────────────
info "Installing dependencies from requirements.txt..."
python3 -m pip install --user -q -r "$SCRIPT_DIR/requirements.txt"
ok "Dependencies ready"

# ── 4. Verify DB connectivity ────────────────────────────────────────────────
info "Checking database connectivity..."
python3 - <<'PYCHECK'
import sys, psycopg2
try:
    conn = psycopg2.connect(
        host="postgresql.thoughts-app.svc.cluster.local",
        database="thoughts",
        user="thoughts",
        password="thoughts123",
        port=5432,
        connect_timeout=5,
    )
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM thoughts")
    count = cur.fetchone()[0]
    conn.close()
    print(f"  Connected – {count} thoughts in database")
except Exception as e:
    print(f"  WARNING: Could not reach database: {e}", file=sys.stderr)
    print("  The app will still start and show an error banner in the browser.")
PYCHECK

# ── 5. Launch ────────────────────────────────────────────────────────────────
echo ""
ok "Starting Flask app on http://0.0.0.0:${PORT}"
echo ""
echo "  Open in browser:  http://localhost:${PORT}"
echo "  Stop:             Ctrl+C"
echo ""

exec python3 "$SCRIPT_DIR/app.py"
