"""Dataclasses exchanged between starter, workflow, and activities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Tier(str, Enum):
    STANDARD = "standard"
    REGULATED = "regulated"


class ProvisioningState(str, Enum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    PROVISIONING_AWS = "PROVISIONING_AWS"
    APPLYING_TERRAFORM = "APPLYING_TERRAFORM"
    CONFIGURING_SERVICES = "CONFIGURING_SERVICES"
    COMPLETED = "COMPLETED"
    DENIED = "DENIED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"


class Scenario(str, Enum):
    HAPPY_PATH = "happy_path"
    APPROVAL_DENIED = "approval_denied"
    TRANSIENT_FAILURE = "transient_failure"
    HARD_FAILURE_COMPENSATION = "hard_failure_compensation"


@dataclass
class TeamRequest:
    """Input to the workflow — describes the team being onboarded."""

    name: str
    tier: str  # Tier enum value — typed as str; Temporal's converter char-splits str-subclass enums
    modules: list[str] = field(default_factory=list)
    owner_email: str = ""
    cost_center: str = ""
    scenario: str = Scenario.HAPPY_PATH  # demo injection hint; ignored in production


@dataclass
class ApprovalDecision:
    """Payload for the security-approval Update."""

    approved: bool
    reason: str
    approver: str = ""


@dataclass
class AWSAccountResult:
    account_id: str
    account_alias: str


@dataclass
class TerraformResult:
    module: str
    outputs: dict[str, str] = field(default_factory=dict)
    stdout_tail: str = ""


@dataclass
class RepoResult:
    url: str


@dataclass
class JiraProjectResult:
    key: str


@dataclass
class ProvisioningProgress:
    """Returned by the `get_progress` query."""

    # str, not ProvisioningState — Temporal's data converter doesn't round-trip
    # str-subclass enums correctly through dataclass field type hints.
    state: str
    completed_steps: list[str] = field(default_factory=list)
    aws_account: AWSAccountResult | None = None
    terraform: TerraformResult | None = None
    repo: RepoResult | None = None
    jira: JiraProjectResult | None = None
    approval: ApprovalDecision | None = None
