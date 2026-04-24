#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Step 5: Scenario — transient_failure
#
# apply_terraform_networking fails on attempt 1, succeeds on attempt 2.
# Shows how Temporal's retry policy handles transient errors transparently.
#
# Watch the Temporal UI event history — you'll see:
#   ActivityTaskFailed  (attempt 1)
#   ActivityTaskStarted (attempt 2)
#   ActivityTaskCompleted
# The workflow continues to COMPLETED as if nothing happened.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  5 / 7  Scenario: transient_failure      ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "apply_terraform_networking raises on attempt 1, succeeds on attempt 2."
echo "The retry is automatic — the workflow reaches COMPLETED."
echo ""
echo -e "${YELLOW}Tip: open the Temporal UI event history after approving${NC}"
echo -e "${YELLOW}     to see the failed attempt alongside the successful retry.${NC}"
echo ""

echo "Starting workflow..."
STARTER_OUTPUT=$(uv run python starter.py --request requests/team_phoenix.yaml --scenario transient_failure)
echo "$STARTER_OUTPUT"

WORKFLOW_ID=$(echo "$STARTER_OUTPUT" | grep "ID:" | awk '{print $2}')

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  Workflow is paused at AWAITING_APPROVAL  ${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Open the Temporal UI:"
echo "  http://localhost:8233"
echo ""
read -rp "Press Enter to approve and watch the retry happen... "

echo ""
echo "Sending approval..."
uv run python approve.py \
  --workflow-id "$WORKFLOW_ID" \
  --approved \
  --reason "all controls verified by security team" \
  --approver "demo"

echo ""
echo -e "${BOLD}Watching progress — terraform will fail once, then retry...${NC}"
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
  echo -e "${GREEN}✓ Workflow COMPLETED despite the transient failure — retry handled it.${NC}"
  echo ""
  echo "  Check the Temporal UI event history for ActivityTaskFailed on attempt 1."
fi

echo ""
echo -e "${BOLD}Next:${NC} run  scripts/06_hard_failure_compensation.sh"
