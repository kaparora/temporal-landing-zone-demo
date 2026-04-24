"""Demo scenario failure injection.

Activities call maybe_inject_failure(scenario, step) to raise predictable
errors so each demo scenario is reproducible without touching real systems.
Only raises on the specific (scenario, step) combination; all others are no-ops.
"""

from __future__ import annotations

from temporalio import activity
from temporalio.exceptions import ApplicationError


def maybe_inject_failure(scenario: str, step: str) -> None:
    """Raise if this step should fail for the given demo scenario. No-op otherwise."""

    if scenario == "transient_failure" and step == "apply_terraform_networking":
        # Fail only on the first attempt so the retry succeeds and shows in history.
        if activity.info().attempt == 1:
            raise ApplicationError(
                "Simulated transient failure: Terraform state lock timeout — will retry",
                non_retryable=False,
            )

    elif scenario == "hard_failure_compensation" and step == "create_github_repo":
        # Non-retryable so Temporal skips retries and the saga fires immediately.
        raise ApplicationError(
            "GitHub API error: repository creation blocked — org limit exceeded (HTTP 422)",
            non_retryable=True,
        )
