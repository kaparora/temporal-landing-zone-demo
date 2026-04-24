"""Unit test for LandingZoneWorkflow using Temporal's time-skipping test environment.

All activities are replaced with fast mocks so the test runs without Terraform,
AWS credentials, or a running Temporal server. The time-skipping environment
accelerates any asyncio.sleep calls inside the workflow or activities.
"""

from __future__ import annotations

import asyncio

import pytest
from temporalio import activity
from temporalio.client import WorkflowUpdateFailedError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from landing_zone.models import (
    ApprovalDecision,
    AWSAccountResult,
    JiraProjectResult,
    ProvisioningState,
    RepoResult,
    TeamRequest,
    TerraformResult,
    Tier,
)
from landing_zone.workflows import LandingZoneWorkflow

_TASK_QUEUE = "test-landing-zone"


# ── Mock activities ────────────────────────────────────────────────────────────
# Each mock carries the same @activity.defn name as the real implementation so
# the workflow's execute_activity calls route to these stubs during testing.

@activity.defn(name="validate_request")
async def mock_validate(req: TeamRequest) -> None:
    pass


@activity.defn(name="provision_aws_account")
async def mock_provision_aws(req: TeamRequest) -> AWSAccountResult:
    return AWSAccountResult(account_id="111122223333", account_alias="finco-team-test")


@activity.defn(name="apply_terraform_networking")
async def mock_terraform_networking(req: TeamRequest) -> TerraformResult:
    return TerraformResult(
        module="networking",
        outputs={"vpc_id": "vpc-abc123", "subnet_cidr": "10.1.0.0/24"},
        stdout_tail="Apply complete! Resources: 6 added.",
    )


@activity.defn(name="apply_terraform_iam")
async def mock_terraform_iam(req: TeamRequest) -> None:
    pass


@activity.defn(name="create_github_repo")
async def mock_github(req: TeamRequest) -> RepoResult:
    return RepoResult(url=f"https://github.com/finco/{req.name}")


@activity.defn(name="create_jira_project")
async def mock_jira(req: TeamRequest) -> JiraProjectResult:
    return JiraProjectResult(key="TEAMTEST")


@activity.defn(name="bootstrap_observability")
async def mock_observability(req: TeamRequest) -> None:
    pass


@activity.defn(name="notify_team")
async def mock_notify(req: TeamRequest) -> None:
    pass


@activity.defn(name="destroy_terraform_networking")
async def mock_destroy_networking(req: TeamRequest) -> None:
    pass


@activity.defn(name="cleanup_aws_account")
async def mock_cleanup_aws(account: AWSAccountResult) -> None:
    pass


_MOCK_ACTIVITIES = [
    mock_validate,
    mock_provision_aws,
    mock_terraform_networking,
    mock_terraform_iam,
    mock_github,
    mock_jira,
    mock_observability,
    mock_notify,
    mock_destroy_networking,
    mock_cleanup_aws,
]


# ── Tests ──────────────────────────────────────────────────────────────────────

async def test_happy_path_completes():
    """Approved workflow runs all 9 steps and reaches COMPLETED state."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[LandingZoneWorkflow],
            activities=_MOCK_ACTIVITIES,
        ):
            request = TeamRequest(
                name="team-test",
                tier=Tier.REGULATED,
                modules=["networking", "iam"],
                scenario="happy_path",
            )
            handle = await env.client.start_workflow(
                LandingZoneWorkflow.run,
                request,
                id="test-happy-path",
                task_queue=_TASK_QUEUE,
            )

            # Poll until the workflow is waiting for security approval.
            for _ in range(50):
                status = await handle.query(LandingZoneWorkflow.get_status)
                if status == ProvisioningState.AWAITING_APPROVAL:
                    break
                await asyncio.sleep(0.1)
            else:
                pytest.fail("Workflow never reached AWAITING_APPROVAL")

            await handle.execute_update(
                LandingZoneWorkflow.security_approval,
                ApprovalDecision(
                    approved=True,
                    reason="all controls verified by security team",
                    approver="test",
                ),
            )

            result = await handle.result()

        assert result.state == "COMPLETED"
        assert result.completed_steps == [
            "validate_request",
            "security_approval",
            "provision_aws_account",
            "apply_terraform_networking",
            "apply_terraform_iam",
            "create_github_repo",
            "create_jira_project",
            "bootstrap_observability",
            "notify_team",
        ]
        assert result.aws_account == AWSAccountResult(
            account_id="111122223333", account_alias="finco-team-test"
        )
        assert result.terraform is not None
        assert result.terraform.outputs["vpc_id"] == "vpc-abc123"
        assert result.repo == RepoResult(url="https://github.com/finco/team-test")


async def test_approval_validator_rejects_short_reason():
    """Validator rejects an approval reason shorter than 10 characters."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[LandingZoneWorkflow],
            activities=_MOCK_ACTIVITIES,
        ):
            request = TeamRequest(name="team-test2", tier=Tier.REGULATED, scenario="happy_path")
            handle = await env.client.start_workflow(
                LandingZoneWorkflow.run,
                request,
                id="test-validator",
                task_queue=_TASK_QUEUE,
            )

            for _ in range(50):
                status = await handle.query(LandingZoneWorkflow.get_status)
                if status == ProvisioningState.AWAITING_APPROVAL:
                    break
                await asyncio.sleep(0.1)

            with pytest.raises(WorkflowUpdateFailedError) as exc_info:
                await handle.execute_update(
                    LandingZoneWorkflow.security_approval,
                    ApprovalDecision(approved=True, reason="too short", approver="test"),
                )
            assert "10 characters" in str(exc_info.value.cause)

            # Workflow is still alive and waiting — send a valid approval to clean up.
            await handle.execute_update(
                LandingZoneWorkflow.security_approval,
                ApprovalDecision(approved=True, reason="approved after validator test", approver="test"),
            )
            result = await handle.result()

        assert result.state == ProvisioningState.COMPLETED
