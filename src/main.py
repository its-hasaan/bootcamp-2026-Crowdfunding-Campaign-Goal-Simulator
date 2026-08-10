# =============================================================================
# MODULE 7: Entry Point / Runner
# =============================================================================
# Wires modules 1 to 6 together into a runnable simulation.
#
# Flow
# ----
#  1. Create a Campaign (Module 1)
#  2. Start background deadline checker thread (Module 4)
#  3. Spawn N concurrent backer threads via LoadSimulator (Module 5)
#  4. Wait for all threads to finish
#  5. Close campaign and resolve status via verifier (Module 6)
# =============================================================================

import threading
import time

from campaign       import Campaign
from pledge_engine  import pledge
from progress       import get_progress
from deadline       import start_deadline_checker_thread
from load_simulator import LoadSimulator
from verifier       import verify_results, print_summary


# =============================================================================
# Configuration
# =============================================================================
CAMPAIGN_TITLE    = "Open-Source Rover Project"
GOAL_AMOUNT       = 10_000.00   # $10,000 funding target
CAMPAIGN_DURATION = 10          # campaign lives for 10 seconds (local demo)

NUM_BACKERS       = 100         # threads to spawn concurrently
PLEDGE_AMOUNT     = 100.00      # each backer pledges $100 -> expected total = $10,000


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
