#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Step 3: Scenario — happy_path
#
# All 9 steps succeed end-to-end.
# Shows: validate → approval gate → AWS provisioning →
#        real Terraform apply → 5 service config steps → COMPLETED
#
# You will be prompted to approve before provisioning starts.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  3 / 7  Scenario: happy_path             ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "All 9 activities succeed. Demonstrates the full provisioning flow."
echo ""

# Start workflow and capture output to extract the workflow ID.
echo "Starting workflow..."
STARTER_OUTPUT=$(uv run python starter.py --request requests/team_phoenix.yaml --scenario happy_path)
echo "$STARTER_OUTPUT"

WORKFLOW_ID=$(echo "$STARTER_OUTPUT" | grep "ID:" | awk '{print $2}')

# Starter already waited for AWAITING_APPROVAL — safe to approve now.
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  Workflow is paused at AWAITING_APPROVAL  ${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Open the Temporal UI to see the live state:"
echo "  http://localhost:8233"
echo ""
read -rp "Press Enter to send security approval and start provisioning... "

echo ""
echo "Sending approval..."
uv run python approve.py \
  --workflow-id "$WORKFLOW_ID" \
  --approved \
  --reason "all controls verified by security team" \
  --approver "demo"

echo ""
echo -e "${BOLD}Watching progress (query every 2s)...${NC}"
echo ""
while true; do
  STATUS=$(temporal workflow query --workflow-id "$WORKFLOW_ID" --type get_status 2>&1 \
           | grep QueryResult | awk '{print $2}' | tr -d '"')
  echo "  $(date +%H:%M:%S)  state: ${BOLD}${STATUS}${NC}"
  case "$STATUS" in
    COMPLETED|COMPENSATED|DENIED|FAILED) break ;;
  esac
  sleep 2
done

echo ""
if [[ "$STATUS" == "COMPLETED" ]]; then
  echo -e "${GREEN}✓ Workflow COMPLETED — all 9 steps succeeded.${NC}"
else
  echo -e "${YELLOW}Final state: $STATUS${NC}"
fi

echo ""
echo -e "${BOLD}Next:${NC} run  scripts/04_approval_denied.sh"
