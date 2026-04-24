#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Step 1: Start the Temporal dev server
# Run this ONCE at the start of a demo session.
# Leave it running; open the next script in a new tab/pane.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  1 / 7  Start Temporal Dev Server        ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

if pgrep -f "temporal server start-dev" > /dev/null 2>&1; then
  echo -e "${YELLOW}Server is already running.${NC}"
  echo "  UI: http://localhost:8233"
  exit 0
fi

echo "Starting server..."
temporal server start-dev --log-level warn &

echo "Waiting for server to be ready..."
for i in $(seq 1 15); do
  sleep 1
  if temporal operator namespace list > /dev/null 2>&1; then
    break
  fi
done

echo ""
echo -e "${GREEN}✓ Temporal server is ready${NC}"
echo ""
echo "  UI → http://localhost:8233"
echo ""
echo -e "${BOLD}Next:${NC} open a new terminal tab and run  scripts/02_start_worker.sh"
echo ""
echo "(This process stays in the foreground — keep this tab open)"
wait   # keep server alive
