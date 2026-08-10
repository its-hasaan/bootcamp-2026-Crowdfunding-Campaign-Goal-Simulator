# =============================================================================
# Temporal Worker: Hosts Workflows and Activities
# =============================================================================
# The Worker process connects to the Temporal server, registers our
# CampaignWorkflow and activities, and polls the "crowdfunding-task-queue"
# for tasks to execute.
#
# Run this in a dedicated terminal:
#   python -m src.temporal_app.worker
#
# Prerequisites:
#   1. Temporal dev server running:  temporal server start-dev
#   2. temporalio installed:         pip install temporalio
#
# Temporal 102 — Deploying to Production: the Client connection is built by
# get_temporal_client() (client_config.py), which reads TEMPORAL_ADDRESS /
# TEMPORAL_NAMESPACE / TEMPORAL_API_KEY / TLS env vars. No code here changes
# when this Worker is deployed against a self-hosted Cluster or Temporal
# Cloud — only environment variables do.
# =============================================================================

import asyncio
from temporalio.worker import Worker

from src.temporal_app.client_config import get_temporal_client
from src.temporal_app.workflows import CampaignWorkflow
from src.temporal_app.activities import (
    validate_campaign_activity,
    log_pledge_activity,
    log_campaign_result_activity,
)

TASK_QUEUE = "crowdfunding-task-queue"


async def main():
    """Connect to Temporal and start the worker."""
    print("=" * 70)
    print("  TEMPORAL WORKER — Crowdfunding Campaign Simulator")
    print("=" * 70)
    print(f"\n  Connecting to Temporal...")

    client = await get_temporal_client()

    print(f"  Connected! Starting worker on task queue: '{TASK_QUEUE}'")
    print(f"  Registered workflow:  CampaignWorkflow")
    print(
        f"  Registered activities: validate_campaign_activity, "
        f"log_pledge_activity, log_campaign_result_activity"
    )
    print(f"\n  Worker is running. Press Ctrl+C to stop.\n")
    print("=" * 70 + "\n")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CampaignWorkflow],
        activities=[
            validate_campaign_activity,
            log_pledge_activity,
            log_campaign_result_activity,
        ],
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
