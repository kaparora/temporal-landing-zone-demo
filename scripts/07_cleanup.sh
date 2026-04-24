#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Step 7: Clean up — stop worker + server, destroy AWS resources
#
#   1. Kill the worker and Temporal dev server processes
#   2. terraform destroy against the networking module
#      (removes the real VPC + subnet + IGW + route table)
#
# Safe to re-run. If there's nothing to destroy or nothing to
# kill, it says so and moves on.
# ─────────────────────────────────────────────────────────────
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  7 / 7  Cleanup                          ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Stop processes ────────────────────────────────────────
if pkill -f "python worker.py" 2>/dev/null; then
  echo -e "${GREEN}✓ Worker stopped${NC}"
else
  echo -e "${YELLOW}  Worker was not running${NC}"
fi

if pkill -f "temporal server start-dev" 2>/dev/null; then
  echo -e "${GREEN}✓ Temporal server stopped${NC}"
else
  echo -e "${YELLOW}  Server was not running${NC}"
fi

# ── 2. Destroy AWS resources (if any) ────────────────────────
export AWS_PROFILE="${AWS_PROFILE:-demo}"

if [ -d terraform/networking/.terraform ]; then
  echo ""
  echo -e "${BLUE}Running terraform destroy (AWS profile: ${AWS_PROFILE})...${NC}"
  echo ""
  terraform -chdir=terraform/networking destroy \
    -auto-approve \
    -input=false \
    -no-color \
    -var "team_name=team-phoenix"
  echo ""
  echo -e "${GREEN}✓ AWS resources destroyed${NC}"
else
  echo ""
  echo -e "${YELLOW}  Terraform not initialized — nothing to destroy${NC}"
fi

echo ""
echo -e "${BOLD}Done. Slate is clean.${NC}"
echo ""
