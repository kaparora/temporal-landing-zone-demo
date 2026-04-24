"""Workflow starter — loads a team request YAML and kicks off LandingZoneWorkflow.

Usage:
  uv run python starter.py --request requests/team_phoenix.yaml --scenario happy_path
  uv run python starter.py --request requests/team_phoenix.yaml --scenario approval_denied
  uv run python starter.py --request requests/team_phoenix.yaml --scenario transient_failure
  uv run python starter.py --request requests/team_phoenix.yaml --scenario hard_failure_compensation
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

import yaml
from temporalio.client import Client, TLSConfig
from temporalio.exceptions import WorkflowAlreadyStartedError

from landing_zone.config import load_settings
from landing_zone.models import Scenario, TeamRequest
from landing_zone.workflows import LandingZoneWorkflow


async def main(request_path: str, scenario: str) -> None:
    settings = load_settings()
    client = await _connect(settings)

    with open(request_path) as f:
        data = yaml.safe_load(f)

    request = TeamRequest(
        name=data["name"],
        tier=data["tier"],
        modules=data.get("modules", []),
        owner_email=data.get("owner_email", ""),
        cost_center=data.get("cost_center", ""),
        scenario=scenario,
    )

    workflow_id = f"landing-zone-{request.name}-{uuid.uuid4().hex[:8]}"

    handle = await client.start_workflow(
        LandingZoneWorkflow.run,
        request,
        id=workflow_id,
        task_queue=settings.temporal.task_queue,
    )

    ui_url = (
        f"http://localhost:8233/namespaces/{settings.temporal.namespace}"
        f"/workflows/{workflow_id}"
    )
    print(f"\nWorkflow started")
    print(f"  ID:       {workflow_id}")
    print(f"  Team:     {request.name} ({request.tier})")
    print(f"  Scenario: {scenario}")
    print(f"  UI:       {ui_url}")

    # Poll until the workflow actually reaches AWAITING_APPROVAL before
    # printing the approve command — avoids the race where the user sends
    # the Update before validate_request completes.
    print("\nWaiting for security approval gate...", end="", flush=True)
    for _ in range(60):
        status = await handle.query(LandingZoneWorkflow.get_status)
        if status == "AWAITING_APPROVAL":
            break
        await asyncio.sleep(0.5)
    print(" ready.")
    print(f"\nTo approve:  uv run python approve.py --workflow-id {workflow_id} --approved --reason 'all controls verified by security'")
    print(f"To deny:     uv run python approve.py --workflow-id {workflow_id} --reason 'missing compliance controls'")


async def _connect(settings):
    if settings.temporal.api_key:
        return await Client.connect(
            settings.temporal.address,
            namespace=settings.temporal.namespace,
            api_key=settings.temporal.api_key,
            tls=TLSConfig(),
        )
    if settings.temporal.tls.enabled:
        return await Client.connect(
            settings.temporal.address,
            namespace=settings.temporal.namespace,
            tls=TLSConfig(),
        )
    return await Client.connect(
        settings.temporal.address,
        namespace=settings.temporal.namespace,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start a LandingZoneWorkflow")
    parser.add_argument("--request", required=True, help="Path to team request YAML")
    parser.add_argument(
        "--scenario",
        default=Scenario.HAPPY_PATH,
        choices=[s.value for s in Scenario],
        help="Demo scenario (default: happy_path)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.request, args.scenario))
