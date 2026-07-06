# =============================================================================
# Temporal Client: Run the Crowdfunding Simulation
# =============================================================================
# This script replaces main.py for the Temporal version of the simulator.
#
# Flow:
#   1. Connect to the local Temporal server.
#   2. Start a CampaignWorkflow execution.
#   3. Send N pledge signals concurrently (simulating concurrent backers).
#   4. Query progress while the campaign runs.
#   5. Wait for the workflow to complete.
#   6. Print the final verification report.
#
# Run:
#   python -m src.temporal_app.run_simulation
#
# Prerequisites:
#   1. Temporal dev server running:  temporal server start-dev
#   2. Worker running:               python -m src.temporal_app.worker
# =============================================================================

import asyncio
import time
from temporalio.client import Client

from src.temporal_app.workflows import CampaignWorkflow, CampaignInput, PledgeData

# =============================================================================
# Configuration (mirrors main.py settings)
# =============================================================================
CAMPAIGN_TITLE    = "Open-Source Rover Project"
GOAL_AMOUNT       = 10_000.00   # $10,000 funding target
CAMPAIGN_DURATION = 10          # campaign lives for 10 seconds
NUM_BACKERS       = 100         # concurrent pledge signals to send
PLEDGE_AMOUNT     = 100.00      # each backer pledges $100 -> expected total = $10,000

TASK_QUEUE        = "crowdfunding-task-queue"
TEMPORAL_SERVER   = "localhost:7233"
WORKFLOW_ID       = f"crowdfunding-campaign-{int(time.time())}"


async def main():
    """Run the full crowdfunding simulation via Temporal."""
    print("=" * 70)
    print("  CROWDFUNDING CAMPAIGN SIMULATOR -- Temporal Workflow Edition")
    print("=" * 70)
    print(f"\n  Campaign: {CAMPAIGN_TITLE}")
    print(f"  Goal amount: ${GOAL_AMOUNT:,.2f}")
    print(f"  Campaign duration: {CAMPAIGN_DURATION}s")
    print(f"  Number of concurrent backers: {NUM_BACKERS}")
    print(f"  Pledge amount per backer: ${PLEDGE_AMOUNT:.2f}")
    print("=" * 70)

    # --- Connect to Temporal ---
    print(f"\n  Connecting to Temporal server at {TEMPORAL_SERVER}...")
    client = await Client.connect(TEMPORAL_SERVER)
    print("  Connected!\n")

    # --- Start the Campaign Workflow ---
    campaign_input = CampaignInput(
        title=CAMPAIGN_TITLE,
        goal_amount=GOAL_AMOUNT,
        duration_sec=CAMPAIGN_DURATION,
        num_backers=NUM_BACKERS,
        pledge_amount=PLEDGE_AMOUNT,
    )

    print(f"  Starting CampaignWorkflow (id={WORKFLOW_ID})...")
    handle = await client.start_workflow(
        CampaignWorkflow.run,
        campaign_input,
        id=WORKFLOW_ID,
        task_queue=TASK_QUEUE,
    )
    print(f"  Workflow started! Sending {NUM_BACKERS} pledge signals...\n")

    # --- Send pledge signals concurrently ---
    # This replaces the LoadSimulator's ThreadPoolExecutor.
    # All signals are sent at roughly the same time, but Temporal
    # processes them sequentially inside the workflow — no races.
    start = time.time()

    async def send_pledge(backer_num: int):
        pledge_data = PledgeData(
            backer_id=f"backer_{backer_num:04d}",
            amount=PLEDGE_AMOUNT,
        )
        await handle.signal(CampaignWorkflow.pledge_signal, pledge_data)

    # Fire all pledge signals concurrently
    await asyncio.gather(*(send_pledge(i) for i in range(NUM_BACKERS)))

    elapsed = time.time() - start
    print(f"\n  All {NUM_BACKERS} pledge signals sent in {elapsed:.3f}s")

    # --- Query progress while campaign is still running ---
    try:
        progress = await handle.query(CampaignWorkflow.get_progress)
        print(f"\n  [PROGRESS QUERY]")
        print(f"    Status:       {progress['status'].upper()}")
        print(f"    Pledged:      ${progress['total_pledged']:>10,.2f}")
        print(f"    Goal:         ${progress['goal_amount']:>10,.2f}")
        print(f"    Progress:     {progress['percentage']}%")
        print(f"    Backers:      {progress['backer_count']}")
    except Exception as e:
        print(f"  (Progress query skipped: {e})")

    # --- Wait for the workflow to complete ---
    print(f"\n  Waiting for campaign deadline ({CAMPAIGN_DURATION}s)...\n")
    result = await handle.result()

    # --- Print final summary ---
    print("\n" + "=" * 70)
    print("  SIMULATION COMPLETE — FINAL RESULTS")
    print("=" * 70)

    print(f"\n  Workflow ID:          {WORKFLOW_ID}")
    print(f"  Pledges sent:         {NUM_BACKERS}")
    print(f"  Pledges recorded:     {result['pledge_log_length']}")
    print(f"  Observed total:       ${result['observed']:>10,.2f}")
    print(f"  True total (log):     ${result['expected']:>10,.2f}")
    print(f"  Lost to races:        ${result['lost']:>10,.2f}")
    print(f"  Campaign verdict:     {result['observed_verdict'].upper()}")
    print(f"  True verdict:         {result['true_verdict'].upper()}")

    if not result["has_race_condition"] and not result["verdict_mismatch"]:
        print(f"\n  [OK] PERFECT CONSISTENCY -- Temporal eliminated all race conditions!")
        print(f"  All {result['real_backers']} pledges processed correctly.")
    else:
        print(f"\n  [WARNING] Unexpected discrepancy detected!")

    print(f"\n  View workflow history at: http://localhost:8233")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
