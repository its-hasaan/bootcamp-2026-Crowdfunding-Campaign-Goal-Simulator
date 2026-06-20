# =============================================================================
# MODULE 7: Entry Point / Runner
# =============================================================================
# Wires modules 1 and 2 together into a minimal runnable skeleton.
#
# Flow
# ----
#  1. Create a Campaign (Module 1)
#  2. Spawn N concurrent threads, each calling pledge() (Module 2)
#  3. Wait for all threads to finish
#  4. Print the observed total vs the true total from the pledge log
#     — the mismatch is the race condition in action
#
# Modules 3-6 (progress reporter, deadline checker, load simulator,
# verifier) will plug into the stubs below in the next iteration.
# =============================================================================

import threading
import time

from campaign      import Campaign
from pledge_engine import pledge, get_true_total, get_true_backer_count


# =============================================================================
# Configuration
# =============================================================================
CAMPAIGN_TITLE    = "Open-Source Rover Project"
GOAL_AMOUNT       = 10_000.00   # $10,000 funding target
CAMPAIGN_DURATION = 60          # campaign lives for 60 seconds (local demo)

NUM_BACKERS       = 100         # threads to spawn concurrently
PLEDGE_AMOUNT     = 100.00      # each backer pledges $100 → expected total = $10,000


# =============================================================================
# Stub: Progress Reporter (Module 3 — coming next)
# =============================================================================
def get_progress(campaign: Campaign) -> str:
    """
    Returns a human-readable funding progress string.
    Stub — will be replaced by progress.py in Module 3.
    """
    pct = (campaign.total_pledged / campaign.goal_amount * 100) if campaign.goal_amount else 0
    return (f"${campaign.total_pledged:,.2f} / ${campaign.goal_amount:,.2f} "
            f"— {pct:.1f}%  ({campaign.backer_count} backers)")


# =============================================================================
# Stub: Deadline Checker (Module 4 — coming next)
# =============================================================================
def close_campaign(campaign: Campaign):
    """
    Resolves the campaign after the deadline.
    Stub — will be replaced by deadline.py in Module 4.
    """
    if campaign.total_pledged >= campaign.goal_amount:
        campaign.status = "successful"
    else:
        campaign.status = "failed"


# =============================================================================
# Stub: Load Simulator (Module 5 — coming next)
# =============================================================================
def run_load_simulation(campaign: Campaign):
    """
    Spawns NUM_BACKERS threads that all call pledge() concurrently.
    Stub — will be expanded into load_simulator.py in Module 5.
    """
    threads = []

    for i in range(NUM_BACKERS):
        backer_id = f"backer_{i:04d}"
        # Each thread targets the pledge function with a fixed amount
        t = threading.Thread(
            target=pledge,
            args=(campaign, backer_id, PLEDGE_AMOUNT),
            daemon=True,        # won't block process exit if something hangs
        )
        threads.append(t)

    print(f"\n[SIMULATOR] Launching {NUM_BACKERS} concurrent pledge threads...\n")
    start = time.time()

    # --- Start all threads as close together as possible to maximise overlap ---
    for t in threads:
        t.start()

    # --- Wait for every thread to complete ---
    for t in threads:
        t.join()

    elapsed = time.time() - start
    print(f"\n[SIMULATOR] All threads finished in {elapsed:.3f}s")


# =============================================================================
# Stub: Race Condition Verifier (Module 6 — coming next)
# =============================================================================
def verify_results(campaign: Campaign):
    """
    Compares campaign.total_pledged against the ground-truth pledge log sum.
    Stub — will be replaced by verifier.py in Module 6.
    """
    observed = campaign.total_pledged
    expected = get_true_total()
    lost     = expected - observed
    real_backers = get_true_backer_count()

    print("\n" + "=" * 60)
    print("  RACE CONDITION REPORT")
    print("=" * 60)
    print(f"  Backers who pledged (log) : {real_backers}")
    print(f"  Expected total (log sum)  : ${expected:>10,.2f}")
    print(f"  Observed total (counter)  : ${observed:>10,.2f}")
    print(f"  Lost to race conditions   : ${lost:>10,.2f}")
    print(f"  Campaign status           : {campaign.status.upper()}")

    if lost > 0:
        print(f"\n  *** {lost / expected * 100:.1f}% of pledges were silently dropped! ***")
        if expected >= campaign.goal_amount and campaign.total_pledged < campaign.goal_amount:
            print("  *** Campaign declared FAILED but TRUE total met the goal! ***")
    else:
        print("\n  No lost updates detected this run (try again — it's non-deterministic).")
    print("=" * 60)


# =============================================================================
# Main
# =============================================================================
def main():
    # 1. Create the campaign
    campaign = Campaign(
        title        = CAMPAIGN_TITLE,
        goal_amount  = GOAL_AMOUNT,
        duration_sec = CAMPAIGN_DURATION,
    )

    print("=" * 60)
    print(f"  CAMPAIGN STARTED: {campaign.title}")
    print(f"  Goal    : ${campaign.goal_amount:,.2f}")
    print(f"  Deadline: {CAMPAIGN_DURATION}s from now")
    print("=" * 60)

    # 2. Run the load simulation (concurrent pledges — race conditions here)
    run_load_simulation(campaign)

    # 3. Print live progress as the campaign sees it
    print(f"\n[PROGRESS] {get_progress(campaign)}")

    # 4. Close the campaign (evaluate success/failure)
    close_campaign(campaign)

    # 5. Verify and expose the race condition discrepancy
    verify_results(campaign)


if __name__ == "__main__":
    main()
