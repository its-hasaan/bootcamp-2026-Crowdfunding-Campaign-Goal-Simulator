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
# =============================================================================

import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from src.temporal_app.workflows import CampaignWorkflow
from src.temporal_app.activities import (
    log_pledge_activity,
    log_campaign_result_activity,
)

TASK_QUEUE = "crowdfunding-task-queue"
TEMPORAL_SERVER = "localhost:7233"


async def main():
    """Connect to Temporal and start the worker."""
    print("=" * 70)
    print("  TEMPORAL WORKER — Crowdfunding Campaign Simulator")
    print("=" * 70)
    print(f"\n  Connecting to Temporal server at {TEMPORAL_SERVER}...")

    client = await Client.connect(TEMPORAL_SERVER)

    print(f"  Connected! Starting worker on task queue: '{TASK_QUEUE}'")
    print(f"  Registered workflow:  CampaignWorkflow")
    print(f"  Registered activities: log_pledge_activity, log_campaign_result_activity")
    print(f"\n  Worker is running. Press Ctrl+C to stop.\n")
    print("=" * 70 + "\n")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CampaignWorkflow],
        activities=[
            log_pledge_activity,
            log_campaign_result_activity,
        ],
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
