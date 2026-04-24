"""All activities for the LandingZoneWorkflow.

Real activities: validate_request (1), provision_aws_account (3), apply_terraform_networking (4).
Dummy activities: apply_terraform_iam, create_github_repo, create_jira_project,
                  bootstrap_observability, notify_team (5-9).
Compensation activities: destroy_terraform_networking, cleanup_aws_account.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError

from landing_zone.scenarios import maybe_inject_failure
from landing_zone.models import (
    AWSAccountResult,
    JiraProjectResult,
    RepoResult,
    TeamRequest,
    TerraformResult,
)

_ALLOWED_MODULES = frozenset({"networking", "iam", "github", "jira", "observability"})
_TEAM_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")


# ─── Activity 1: validate_request (scheduled as local activity) ───────────────

@activity.defn
async def validate_request(request: TeamRequest) -> None:
    """Validates team name, tier, and module list. Raises non-retryable on any violation."""
    if not request.name or not _TEAM_NAME_RE.match(request.name):
        raise ApplicationError(
            f"Invalid team name '{request.name}'. "
            "Must be 2-31 chars, lowercase alphanumeric/hyphens, start with a letter.",
            non_retryable=True,
        )
    unknown = set(request.modules) - _ALLOWED_MODULES
    if unknown:
        raise ApplicationError(
            f"Unknown modules: {sorted(unknown)}. Allowed: {sorted(_ALLOWED_MODULES)}",
            non_retryable=True,
        )
    activity.logger.info(
        "Request for '%s' (tier=%s, modules=%s) passed validation",
        request.name,
        request.tier,
        request.modules,
    )


# ─── Activity 3: provision_aws_account ───────────────────────────────────────

_AWS_PROVISION_SECONDS = 18
_HEARTBEAT_INTERVAL = 2


@activity.defn
async def provision_aws_account(request: TeamRequest) -> AWSAccountResult:
    """Simulates async AWS account provisioning with a heartbeat every 2s.

    In a real implementation this would poll the AWS Organizations API until
    the account reaches ACTIVE state (typically 15-30 minutes).
    """
    activity.logger.info(
        "Provisioning AWS account for team '%s' (~%ds)", request.name, _AWS_PROVISION_SECONDS
    )
    elapsed = 0
    while elapsed < _AWS_PROVISION_SECONDS:
        await asyncio.sleep(_HEARTBEAT_INTERVAL)
        elapsed += _HEARTBEAT_INTERVAL
        activity.heartbeat(f"account creation in progress ({elapsed}/{_AWS_PROVISION_SECONDS}s)")
        activity.logger.debug("AWS account heartbeat at %ds", elapsed)

    result = AWSAccountResult(
        account_id=f"12345{abs(hash(request.name)) % 100000:05d}",
        account_alias=f"finco-{request.name}",
    )
    activity.logger.info("AWS account ready: %s (%s)", result.account_id, result.account_alias)
    return result


# ─── Activity 4: apply_terraform_networking ───────────────────────────────────

@activity.defn
async def apply_terraform_networking(request: TeamRequest) -> TerraformResult:
    """Runs terraform init → apply against the networking module.

    Provisions real AWS resources (VPC + public subnet + internet gateway
    + route table) via the hashicorp/aws provider. AWS credentials come
    from the AWS_PROFILE environment variable inherited from the worker
    process. Heartbeats on every line of terraform output so Temporal
    can detect worker crashes during a long apply.
    """
    maybe_inject_failure(request.scenario, "apply_terraform_networking")

    from landing_zone.config import load_settings

    settings = load_settings()
    module = settings.terraform.networking_module
    binary = settings.terraform.binary
    team_var = ["-var", f"team_name={request.name}"]

    os.makedirs(str(module / "outputs"), exist_ok=True)

    activity.logger.info("terraform init for team '%s' in %s", request.name, module)
    activity.heartbeat("terraform init")
    await _run_terraform(binary, module, "init", "-input=false", "-no-color")

    activity.logger.info("terraform apply for team '%s'", request.name)
    apply_out = await _run_terraform(
        binary, module,
        "apply", "-auto-approve", "-input=false", "-no-color", *team_var,
        stream_heartbeats=True,
    )

    activity.heartbeat("terraform output")
    output_json_str = await _run_terraform(binary, module, "output", "-json")
    raw_outputs: dict = json.loads(output_json_str)
    outputs = {k: v["value"] for k, v in raw_outputs.items()}

    result = TerraformResult(
        module="networking",
        outputs=outputs,
        stdout_tail=apply_out[-800:].strip(),
    )
    activity.logger.info(
        "Terraform networking complete for '%s': %s", request.name, outputs
    )
    return result


# ─── Activities 5-9: dummy activities ────────────────────────────────────────

@activity.defn
async def apply_terraform_iam(request: TeamRequest) -> None:
    activity.heartbeat("applying IAM/SSO module")
    await asyncio.sleep(3)
    activity.logger.info("Applied IAM/SSO module for team '%s'", request.name)


@activity.defn
async def create_github_repo(request: TeamRequest) -> RepoResult:
    maybe_inject_failure(request.scenario, "create_github_repo")
    activity.heartbeat("calling GitHub API")
    await asyncio.sleep(2)
    result = RepoResult(url=f"https://github.com/finco/{request.name}")
    activity.logger.info("Created GitHub repo: %s", result.url)
    return result


@activity.defn
async def create_jira_project(request: TeamRequest) -> JiraProjectResult:
    activity.heartbeat("calling Jira API")
    await asyncio.sleep(2)
    key = request.name.upper().replace("-", "")[:6]
    result = JiraProjectResult(key=key)
    activity.logger.info("Created Jira project: %s", result.key)
    return result


@activity.defn
async def bootstrap_observability(request: TeamRequest) -> None:
    activity.heartbeat("configuring Datadog + CloudWatch")
    await asyncio.sleep(3)
    activity.logger.info("Datadog + CloudWatch configured for team '%s'", request.name)


@activity.defn
async def notify_team(request: TeamRequest) -> None:
    activity.heartbeat("sending Slack notification")
    await asyncio.sleep(1)
    payload = {
        "channel": f"#team-{request.name}",
        "text": f":white_check_mark: Landing zone ready! Welcome, {request.name}.",
        "attachments": [{"title": "Next steps", "text": "Check #platform-onboarding for details."}],
    }
    activity.logger.info("Slack notification sent to %s: %s", payload["channel"], payload["text"])


# ─── Compensation activities ──────────────────────────────────────────────────

@activity.defn
async def destroy_terraform_networking(request: TeamRequest) -> None:
    """Runs terraform destroy to undo networking provisioning for a team."""
    from landing_zone.config import load_settings

    settings = load_settings()
    module = settings.terraform.networking_module
    binary = settings.terraform.binary
    team_var = ["-var", f"team_name={request.name}"]

    activity.logger.info(
        "COMPENSATE: terraform destroy for team '%s' in %s", request.name, module
    )
    activity.heartbeat("terraform destroy starting")
    await _run_terraform(
        binary, module,
        "destroy", "-auto-approve", "-input=false", "-no-color", *team_var,
        stream_heartbeats=True,
    )
    activity.logger.info("COMPENSATE: networking resources destroyed for team '%s'", request.name)


@activity.defn
async def cleanup_aws_account(account: AWSAccountResult) -> None:
    activity.logger.info(
        "COMPENSATE: closing AWS account %s (%s)", account.account_id, account.account_alias
    )
    await asyncio.sleep(2)
    activity.logger.info("COMPENSATE: AWS account %s closed", account.account_id)


# ─── Internal helpers ─────────────────────────────────────────────────────────

async def _run_terraform(
    binary: str,
    module_path: Path,
    *args: str,
    stream_heartbeats: bool = False,
) -> str:
    """Runs a terraform subcommand, optionally heartbeating on each output line.

    Raises ApplicationError (retryable) if terraform exits non-zero.
    """
    proc = await asyncio.create_subprocess_exec(
        binary, *args,
        cwd=str(module_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert proc.stdout is not None

    captured: list[str] = []
    async for raw in proc.stdout:
        line = raw.decode(errors="replace")
        captured.append(line)
        if stream_heartbeats:
            activity.heartbeat(line.rstrip()[:120])

    await proc.wait()
    output = "".join(captured)

    if proc.returncode != 0:
        raise ApplicationError(
            f"`terraform {args[0]}` failed (exit {proc.returncode}):\n{output[-2000:]}",
            non_retryable=False,
        )
    return output
