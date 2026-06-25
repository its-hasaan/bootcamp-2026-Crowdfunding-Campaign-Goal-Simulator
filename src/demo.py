# =============================================================================
# DEMO RUNNER — Visual demonstration of the race condition
# =============================================================================
# Run this instead of main.py for a cleaner, visually rich demonstration.
# Usage:  python src/demo.py
# =============================================================================

import sys
import os
import time

# Allow imports from src/ when running directly
sys.path.insert(0, os.path.dirname(__file__))

from campaign      import Campaign
from pledge_engine import pledge as _pledge, get_true_total, get_true_backer_count, pledge_log
from deadline      import start_deadline_checker_thread, close_campaign
from display       import (
    console,
    print_campaign_header,
    print_simulation_start,
    run_with_progress,
    print_progress_bar,
    print_race_condition_report,
)

# ── Config ──────────────────────────────────────────────────────────────────
TITLE         = "Open-Source Rover Project"
GOAL          = 10_000.00
DURATION_SEC  = 10          # short deadline so demo finishes fast
NUM_BACKERS   = 100
PLEDGE_AMOUNT = 100.00
# ────────────────────────────────────────────────────────────────────────────


def main():
    # Clear any state from previous runs
    pledge_log.clear()

    # 1. Create campaign
    campaign = Campaign(TITLE, GOAL, DURATION_SEC)
    print_campaign_header(campaign)

    # 2. Start background deadline checker
    deadline_thread = start_deadline_checker_thread(campaign)

    # 3. Show simulation config
    print_simulation_start(NUM_BACKERS, PLEDGE_AMOUNT)

    # 4. Run load simulation with live progress bar (silent — no per-pledge prints)
    def silent_pledge(campaign, backer_id, amount):
        return _pledge(campaign, backer_id, amount, verbose=False)

    start = time.time()
    run_with_progress(campaign, NUM_BACKERS, silent_pledge, PLEDGE_AMOUNT)
    elapsed = time.time() - start

    console.print(f"\n  [dim]All {NUM_BACKERS} threads finished in {elapsed:.3f}s[/]")

    # 5. Show live progress snapshot (the corrupted counter)
    print_progress_bar(campaign)

    # 6. Wait for deadline checker to close the campaign
    deadline_thread.join()

    # 7. Print the race condition report
    print_race_condition_report(campaign, get_true_total(), get_true_backer_count())


if __name__ == "__main__":
    main()
