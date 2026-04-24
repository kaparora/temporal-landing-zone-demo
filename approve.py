"""Send a security-approval Update to a running LandingZoneWorkflow.

Usage:
  uv run python approve.py --workflow-id <id> --approved --reason 'all controls verified'
  uv run python approve.py --workflow-id <id> --reason 'missing encryption controls'
"""

from __future__ import annotations

import argparse
import asyncio

from temporalio.client import Client, TLSConfig

from landing_zone.config import load_settings
from landing_zone.models import ApprovalDecision
from landing_zone.workflows import LandingZoneWorkflow


async def main(workflow_id: str, approved: bool, reason: str, approver: str) -> None:
    settings = load_settings()
    client = await _connect(settings)

    handle = client.get_workflow_handle(workflow_id)
    decision = ApprovalDecision(approved=approved, reason=reason, approver=approver)

    try:
        result = await handle.execute_update(
            LandingZoneWorkflow.security_approval,
            decision,
        )
        outcome = "APPROVED" if approved else "DENIED"
        print(f"Security approval sent — outcome: {outcome}")
        print(f"  Workflow ID: {workflow_id}")
        print(f"  Approver:    {approver}")
        print(f"  Reason:      {reason}")
        print(f"  Server ack:  {result}")
    except Exception as exc:
        print(f"Update rejected by validator: {exc}")


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
    parser = argparse.ArgumentParser(description="Send a security approval to a LandingZoneWorkflow")
    parser.add_argument("--workflow-id", required=True, help="Workflow ID to approve/deny")
    parser.add_argument("--approved", action="store_true", default=False, help="Approve the request")
    parser.add_argument("--reason", required=True, help="Reason for the decision (min 10 chars)")
    parser.add_argument("--approver", default="cli-user", help="Name of the approver")
    args = parser.parse_args()

    asyncio.run(main(args.workflow_id, args.approved, args.reason, args.approver))
