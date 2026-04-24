"""Smoke test — verifies config loads and core models instantiate correctly."""

from pathlib import Path

from landing_zone.config import load_settings
from landing_zone.models import (
    ApprovalDecision,
    ProvisioningState,
    Scenario,
    TeamRequest,
    Tier,
)


def test_settings_load():
    s = load_settings()
    assert s.temporal.address == "localhost:7233"
    assert s.temporal.namespace == "default"
    assert s.temporal.task_queue == "landing-zone-task-queue"
    assert isinstance(s.terraform.networking_module, Path)
    assert s.terraform.networking_module.exists()


def test_team_request():
    req = TeamRequest(
        name="team-phoenix",
        tier=Tier.REGULATED,
        modules=["networking", "iam"],
        owner_email="phoenix@finco.example.com",
    )
    assert req.name == "team-phoenix"
    assert req.tier == Tier.REGULATED
    assert "networking" in req.modules


def test_approval_decision():
    approved = ApprovalDecision(approved=True, reason="all controls verified", approver="alice")
    denied = ApprovalDecision(approved=False, reason="missing cost center", approver="bob")
    assert approved.approved
    assert not denied.approved


def test_enums():
    assert ProvisioningState.AWAITING_APPROVAL.value == "AWAITING_APPROVAL"
    assert ProvisioningState.COMPENSATED.value == "COMPENSATED"
    assert Scenario.HARD_FAILURE_COMPENSATION.value == "hard_failure_compensation"
    assert Tier.REGULATED.value == "regulated"
