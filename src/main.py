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

from campaign       import Campaign
from pledge_engine  import pledge, get_true_total, get_true_backer_count
from progress       import get_progress
from deadline       import start_deadline_checker_thread
from load_simulator import LoadSimulator
from verifier       import verify_results, print_summary


# =============================================================================
# Configuration
# =============================================================================
CAMPAIGN_TITLE    = "Open-Source Rover Project"
GOAL_AMOUNT       = 10_000.00   # $10,000 funding target
CAMPAIGN_DURATION = 60          # campaign lives for 60 seconds (local demo)

NUM_BACKERS       = 100         # threads to spawn concurrently
PLEDGE_AMOUNT     = 100.00      # each backer pledges $100 → expected total = $10,000








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

    print("=" * 70)
    print(f"  CROWDFUNDING CAMPAIGN SIMULATOR - Demonstrating Race Conditions")
    print("=" * 70)
    print(f"\n  Campaign: {campaign.title}")
    print(f"  Goal amount: ${campaign.goal_amount:,.2f}")
    print(f"  Campaign duration: {CAMPAIGN_DURATION}s")
    print(f"  Number of concurrent backers: {NUM_BACKERS}")
    print(f"  Pledge amount per backer: ${PLEDGE_AMOUNT:.2f}")
    print("=" * 70)

    # 2. Start the deadline checker as a background thread (Module 4)
    deadline_thread = start_deadline_checker_thread(campaign)

    # 3. Run the load simulation (concurrent pledges — race conditions here) (Module 5)
    simulator = LoadSimulator(num_threads=NUM_BACKERS, pledge_amount=PLEDGE_AMOUNT)
    load_result = simulator.run(campaign)

    # 4. Print live progress as the campaign sees it (Module 3)
    print(f"\n[PROGRESS] {get_progress(campaign)}")

    # 5. Wait for the deadline checker to finish resolving the campaign
    deadline_thread.join()

    # 6. Verify and expose the race condition discrepancy (Module 6)
    print_summary(campaign, load_result)


if __name__ == "__main__":
    main()
