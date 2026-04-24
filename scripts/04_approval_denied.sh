#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Step 4: Scenario — approval_denied
#
# Demonstrates Updates-with-validation in two explicit steps:
#
#   Step A: send approval with reason="ok" (too short)
#           → validator rejects BEFORE any workflow state changes
#
#   Step B: send a formal denial with a valid reason
#           → workflow ends cleanly as DENIED (no provisioning)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  4 / 7  Scenario: approval_denied        ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "Demonstrates Update-with-validation:"
echo "  • First attempt rejected by validator (reason too short)"
echo "  • Workflow state is NOT mutated on a rejected Update"
echo "  • Formal denial ends the workflow cleanly as DENIED"
echo ""

# ── Start the workflow ────────────────────────────────────────
echo "Starting workflow..."
STARTER_OUTPUT=$(uv run python starter.py --request requests/team_phoenix.yaml --scenario approval_denied)
echo "$STARTER_OUTPUT"

WORKFLOW_ID=$(echo "$STARTER_OUTPUT" | grep "ID:" | awk '{print $2}')

# ── Step A: attempt with a short reason (validator will reject) ─
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  Workflow is paused at AWAITING_APPROVAL  ${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Open the Temporal UI to see the live state:"
echo "  http://localhost:8233"
echo ""
read -rp "Press Enter to send approval with a short reason (validator will reject it)... "

echo ""
echo "Sending: reason=\"ok\"  (only 2 chars — validator requires ≥ 10)"
uv run python approve.py \
  --workflow-id "$WORKFLOW_ID" \
  --approved \
  --reason "ok" \
  --approver "demo" 2>&1 || true   # expected to fail — don't exit

# ── Step B: formal denial with a valid reason ─────────────────
echo ""
echo -e "${YELLOW}Workflow is still alive and waiting — the rejected Update changed nothing.${NC}"
echo ""
read -rp "Press Enter to send the formal security denial... "

echo ""
echo "Sending formal denial..."
uv run python approve.py \
  --workflow-id "$WORKFLOW_ID" \
  --reason "Security review denied: missing data classification and encryption-at-rest controls." \
  --approver "security-automation"

# ── Poll for terminal state ───────────────────────────────────
echo ""
echo -e "${BOLD}Watching progress...${NC}"
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
if [[ "$STATUS" == "DENIED" ]]; then
  echo -e "${GREEN}✓ Workflow DENIED — no infrastructure was provisioned.${NC}"
fi

echo ""
echo -e "${BOLD}Next:${NC} run  scripts/05_transient_failure.sh"
