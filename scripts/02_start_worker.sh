#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Step 2: Start the Temporal worker
# Run in a second terminal tab. Keep it open — logs stream here.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

BOLD='\033[1m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  2 / 7  Start Worker                     ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "Registers all activities and LandingZoneWorkflow with Temporal."
echo "Activity logs will appear here as scenarios run."
echo ""

# Terraform provisions real AWS resources (VPC + subnet + IGW + route table).
# Override by running:   AWS_PROFILE=<other> ./scripts/02_start_worker.sh
export AWS_PROFILE="${AWS_PROFILE:-demo}"
echo -e "${BLUE}Using AWS profile: ${AWS_PROFILE}${NC}"
echo ""

uv run python worker.py
