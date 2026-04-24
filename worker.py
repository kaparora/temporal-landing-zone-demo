"""Worker entry point — registers workflows and activities with Temporal."""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client, TLSConfig
from temporalio.worker import Worker

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
from landing_zone.config import load_settings
from landing_zone.workflows import LandingZoneWorkflow


async def main() -> None:
    settings = load_settings()

    client = await _connect(settings)

    worker = Worker(
        client,
        task_queue=settings.temporal.task_queue,
        workflows=[LandingZoneWorkflow],
        activities=[
            validate_request,
            provision_aws_account,
            apply_terraform_networking,
            apply_terraform_iam,
            create_github_repo,
            create_jira_project,
            bootstrap_observability,
            notify_team,
            destroy_terraform_networking,
            cleanup_aws_account,
        ],
    )

    logging.info(
        "Worker started | task_queue=%s | namespace=%s | address=%s",
        settings.temporal.task_queue,
        settings.temporal.namespace,
        settings.temporal.address,
    )
    await worker.run()


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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(main())
