#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Step 6: Scenario — hard_failure_compensation
#
# create_github_repo (step 6) raises a non-retryable error AFTER
# AWS and Terraform have already succeeded.
#
# The saga fires in reverse:
#   destroy_terraform_networking  (undoes step 4)
#   cleanup_aws_account           (undoes step 3)
#
# Final state: COMPENSATED  (workflow completes cleanly — no crash)
#
# This is the hardest thing to do in a pipeline and the
# single most compelling demo moment.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  6 / 7  Scenario: hard_failure_          ║${NC}"
echo -e "${BOLD}║          compensation                     ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "create_github_repo fails non-retryably AFTER AWS + Terraform have run."
echo "Saga fires in reverse → workflow ends as COMPENSATED."
echo ""
echo "Completed steps you'll see:"
echo "  validate_request → security_approval → provision_aws_account"
echo "  → apply_terraform_networking → apply_terraform_iam"
echo -e "  → ${RED}✗ create_github_repo (non-retryable failure)${NC}"
echo "  → destroy_terraform_networking  ← compensation"
echo "  → cleanup_aws_account           ← compensation"
echo ""

echo "Starting workflow..."
STARTER_OUTPUT=$(uv run python starter.py --request requests/team_phoenix.yaml --scenario hard_failure_compensation)
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
read -rp "Press Enter to approve and watch the saga fire... "

echo ""
echo "Sending approval..."
uv run python approve.py \
  --workflow-id "$WORKFLOW_ID" \
  --approved \
  --reason "all controls verified by security team" \
  --approver "demo"

echo ""
echo -e "${BOLD}Watching progress — saga will fire after create_github_repo fails...${NC}"
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
if [[ "$STATUS" == "COMPENSATED" ]]; then
  echo -e "${GREEN}✓ Workflow COMPENSATED — prior work unwound cleanly.${NC}"
  echo ""
  echo "Final steps:"
  temporal workflow query --workflow-id "$WORKFLOW_ID" --type get_progress 2>&1 \
    | python3 -c "
import sys, json, re
raw = sys.stdin.read()
m = re.search(r'QueryResult\s+(\{.*\})', raw, re.S)
if m:
    d = json.loads(m.group(1))
    for i, s in enumerate(d['completed_steps'], 1):
        print(f'  {i}. {s}')
"
fi

echo ""
echo -e "${BOLD}Next:${NC} run  scripts/07_cleanup.sh  (when done with the demo)"
