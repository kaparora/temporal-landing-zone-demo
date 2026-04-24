"""LandingZoneWorkflow — orchestrates the 9-step team onboarding saga."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

# Import activity functions and models through the sandbox passthrough so the
# workflow sandbox doesn't try to restrict asyncio/subprocess used in activities.
with workflow.unsafe.imports_passed_through():
    from landing_zone.activities import (
        apply_terraform_iam,
        apply_terraform_networking,
        bootstrap_observability,
        cleanup_aws_account,
        create_github_repo,
        create_jira_project,
        destroy_terraform_networking,
        notify_team,
        provision_aws_account,
        validate_request,
    )
    from landing_zone.models import (
        ApprovalDecision,
        AWSAccountResult,
        JiraProjectResult,
        ProvisioningProgress,
        ProvisioningState,
        RepoResult,
        TeamRequest,
        TerraformResult,
    )

_DEFAULT_ACTIVITY_TIMEOUT = timedelta(seconds=30)
_LONG_ACTIVITY_TIMEOUT = timedelta(minutes=10)
_HEARTBEAT_TIMEOUT = timedelta(seconds=15)
_STANDARD_RETRY = RetryPolicy(maximum_attempts=3)


@workflow.defn
class LandingZoneWorkflow:
    def __init__(self) -> None:
        self._state = ProvisioningState.PENDING
        self._completed_steps: list[str] = []

        # Update-with-validation gate
        self._approval_received: bool = False
        self._approval: ApprovalDecision | None = None

        # Saga bookkeeping — tracks which steps with real side effects have committed
        self._aws_provisioned: bool = False
        self._terraform_applied: bool = False

        # Results (surfaced by get_progress query)
        self._aws_result: AWSAccountResult | None = None
        self._terraform_result: TerraformResult | None = None
        self._repo_result: RepoResult | None = None
        self._jira_result: JiraProjectResult | None = None

    # ── Main execution ────────────────────────────────────────────────────────

    @workflow.run
    async def run(self, request: TeamRequest) -> ProvisioningProgress:
        # 1. Validate request (local activity — fast, no retry needed)
        self._state = ProvisioningState.VALIDATING
        await workflow.execute_local_activity(
            validate_request,
            request,
            start_to_close_timeout=timedelta(seconds=10),
        )
        self._completed_steps.append("validate_request")

        # 2. Security approval gate (Update-with-validation)
        self._state = ProvisioningState.AWAITING_APPROVAL
        await workflow.wait_condition(lambda: self._approval_received)

        assert self._approval is not None
        if not self._approval.approved:
            self._state = ProvisioningState.DENIED
            return self._build_progress()

        self._completed_steps.append("security_approval")

        # 3-9. Provisioning steps wrapped in a saga
        try:
            # 3. AWS account (heartbeated, retried)
            self._state = ProvisioningState.PROVISIONING_AWS
            self._aws_result = await workflow.execute_activity(
                provision_aws_account,
                request,
                start_to_close_timeout=_LONG_ACTIVITY_TIMEOUT,
                heartbeat_timeout=_HEARTBEAT_TIMEOUT,
                retry_policy=_STANDARD_RETRY,
            )
            self._aws_provisioned = True
            self._completed_steps.append("provision_aws_account")

            # 4. Terraform networking (heartbeated, retried)
            self._state = ProvisioningState.APPLYING_TERRAFORM
            self._terraform_result = await workflow.execute_activity(
                apply_terraform_networking,
                request,
                start_to_close_timeout=_LONG_ACTIVITY_TIMEOUT,
                heartbeat_timeout=_HEARTBEAT_TIMEOUT,
                retry_policy=_STANDARD_RETRY,
            )
            self._terraform_applied = True
            self._completed_steps.append("apply_terraform_networking")

            # 5-9. Service configuration (all dummy — one-liners)
            self._state = ProvisioningState.CONFIGURING_SERVICES

            await workflow.execute_activity(
                apply_terraform_iam, request, start_to_close_timeout=_DEFAULT_ACTIVITY_TIMEOUT
            )
            self._completed_steps.append("apply_terraform_iam")

            self._repo_result = await workflow.execute_activity(
                create_github_repo, request, start_to_close_timeout=_DEFAULT_ACTIVITY_TIMEOUT
            )
            self._completed_steps.append("create_github_repo")

            self._jira_result = await workflow.execute_activity(
                create_jira_project, request, start_to_close_timeout=_DEFAULT_ACTIVITY_TIMEOUT
            )
            self._completed_steps.append("create_jira_project")

            await workflow.execute_activity(
                bootstrap_observability, request, start_to_close_timeout=_DEFAULT_ACTIVITY_TIMEOUT
            )
            self._completed_steps.append("bootstrap_observability")

            await workflow.execute_activity(
                notify_team, request, start_to_close_timeout=_DEFAULT_ACTIVITY_TIMEOUT
            )
            self._completed_steps.append("notify_team")

            self._state = ProvisioningState.COMPLETED

        except Exception:
            workflow.logger.exception(
                "Activity failed for team '%s' — triggering saga compensation", request.name
            )
            await self._compensate(request)

        return self._build_progress()

    # ── Saga compensation (runs in reverse order of committed steps) ──────────

    async def _compensate(self, request: TeamRequest) -> None:
        self._state = ProvisioningState.COMPENSATING
        # Reverse order: terraform first, then AWS (mirrors commit order)
        if self._terraform_applied:
            await workflow.execute_activity(
                destroy_terraform_networking,
                request,
                start_to_close_timeout=_LONG_ACTIVITY_TIMEOUT,
                retry_policy=_STANDARD_RETRY,
            )
            self._completed_steps.append("destroy_terraform_networking")
        if self._aws_provisioned and self._aws_result is not None:
            await workflow.execute_activity(
                cleanup_aws_account,
                self._aws_result,
                start_to_close_timeout=_LONG_ACTIVITY_TIMEOUT,
                retry_policy=_STANDARD_RETRY,
            )
            self._completed_steps.append("cleanup_aws_account")
        self._state = ProvisioningState.COMPENSATED

    # ── Update: security_approval (with validator) ────────────────────────────

    @workflow.update
    async def security_approval(self, decision: ApprovalDecision) -> str:
        self._approval = decision
        self._approval_received = True
        outcome = "approved" if decision.approved else "denied"
        workflow.logger.info(
            "Security approval %s by '%s': %s", outcome, decision.approver, decision.reason
        )
        return outcome

    @security_approval.validator
    def _validate_security_approval(self, decision: ApprovalDecision) -> None:
        if self._state != ProvisioningState.AWAITING_APPROVAL:
            raise ApplicationError(
                f"Cannot submit approval: workflow is in state '{self._state.value}', "
                "expected 'AWAITING_APPROVAL'",
                non_retryable=True,
            )
        if len(decision.reason.strip()) < 10:
            raise ApplicationError(
                "Approval reason must be at least 10 characters",
                non_retryable=True,
            )

    # ── Queries ───────────────────────────────────────────────────────────────

    @workflow.query
    def get_status(self) -> str:
        return self._state.value

    @workflow.query
    def get_progress(self) -> ProvisioningProgress:
        return self._build_progress()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_progress(self) -> ProvisioningProgress:
        return ProvisioningProgress(
            state=self._state.value,
            completed_steps=list(self._completed_steps),
            aws_account=self._aws_result,
            terraform=self._terraform_result,
            repo=self._repo_result,
            jira=self._jira_result,
            approval=self._approval,
        )
