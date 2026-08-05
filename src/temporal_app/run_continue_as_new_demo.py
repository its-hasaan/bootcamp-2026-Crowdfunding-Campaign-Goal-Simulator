# =============================================================================
# Temporal 102 Showcase — Continue-As-New in action
# =============================================================================
# The default simulation (run_simulation.py) uses a high
# `continue_as_new_after` threshold, so a normal 100-backer campaign never
# triggers Continue-As-New — Event History stays small on its own.
#
# This script deliberately sets a LOW threshold and sends more signals than
# that threshold, forcing CampaignWorkflow to call `workflow.continue_as_new`
# multiple times so you can observe it happening.
#
# What to look for in the Web UI (http://localhost:8233):
#   - The same Workflow ID persists across the whole campaign.
#   - Under "Recent events" / the Run history, you'll see multiple *Runs*
#     (different Run IDs) for that one Workflow ID — each one is a fresh,
#     small Event History that picked up where the last one left off.
#   - Worker log lines starting with "[CONTINUE-AS-NEW]" mark the handoff.
#
# Run (after starting the dev server + worker):
#   temporal server start-dev
#   python -m src.temporal_app.worker
#   python -m src.temporal_app.run_continue_as_new_demo
# =============================================================================

import asyncio
import time
from temporalio.common import WorkflowIDReusePolicy

from src.temporal_app.client_config import get_temporal_client
from src.temporal_app.workflows import CampaignWorkflow, CampaignInput, PledgeData

TASK_QUEUE = "crowdfunding-task-queue"

# Deliberately low so a single campaign triggers Continue-As-New several
# times. In a real application this would be in the thousands.
CONTINUE_AS_NEW_AFTER = 10

NUM_BACKERS = 45
CAMPAIGN_DURATION = 20
GOAL_AMOUNT = 2_000.00
PLEDGE_AMOUNT = 50.00

WORKFLOW_ID = f"crowdfunding-102-showcase-{int(time.time())}"


async def main():
    print("=" * 70)
    print("  TEMPORAL 102 SHOWCASE — Continue-As-New")
    print("=" * 70)
    print(f"\n  continue_as_new_after = {CONTINUE_AS_NEW_AFTER} signals/generation")
    print(f"  Sending {NUM_BACKERS} pledge signals -> expect multiple Runs\n")

    client = await get_temporal_client()

    campaign_input = CampaignInput(
        title="Temporal 102 Showcase Campaign",
        goal_amount=GOAL_AMOUNT,
        duration_sec=CAMPAIGN_DURATION,
        num_backers=NUM_BACKERS,
        pledge_amount=PLEDGE_AMOUNT,
        continue_as_new_after=CONTINUE_AS_NEW_AFTER,
    )

    handle = await client.start_workflow(
        CampaignWorkflow.run,
        campaign_input,
        id=WORKFLOW_ID,
        task_queue=TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
    )
    print(f"  Workflow started: {WORKFLOW_ID}")
    print(f"  Web UI: http://localhost:8233/namespaces/default/workflows/{WORKFLOW_ID}\n")

    # Stagger signals slightly so multiple Continue-As-New cycles are easy
    # to see in the logs rather than happening all at once.
    for i in range(NUM_BACKERS):
        await handle.signal(
            CampaignWorkflow.pledge_signal,
            PledgeData(backer_id=f"backer_{i:04d}", amount=PLEDGE_AMOUNT),
        )
        await asyncio.sleep(0.2)

        if (i + 1) % CONTINUE_AS_NEW_AFTER == 0:
            progress = await handle.query(CampaignWorkflow.get_progress)
            print(
                f"  ...sent {i + 1} signals -> current generation "
                f"{progress['generation']}, pledged=${progress['total_pledged']:,.2f}"
            )

    result = await handle.result()

    print("\n" + "=" * 70)
    print("  SHOWCASE COMPLETE")
    print("=" * 70)
    print(f"\n  Final generation reached: {result['generation']}")
    print(f"  Total pledged:            ${result['observed']:,.2f}")
    print(f"  Real backers recorded:    {result['real_backers']}")
    print(f"  Verdict:                  {result['observed_verdict'].upper()}")
    print(
        f"\n  Open the Web UI link above and check the Run history for "
        f"{result['generation']} separate Runs under this one Workflow ID."
    )
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
