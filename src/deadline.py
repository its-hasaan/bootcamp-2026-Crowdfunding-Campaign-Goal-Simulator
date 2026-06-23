# =============================================================================
# MODULE 4: Deadline Checker
# =============================================================================
# Runs as a background thread monitoring the campaign deadline.
# When the deadline passes, resolves the campaign status:
#   - If total_pledged >= goal_amount  →  status = "successful"
#   - Otherwise                        →  status = "failed"
#
# This is an "all-or-nothing" model like real Kickstarter campaigns.
# The campaign stops accepting pledges when is_live() returns False.
# =============================================================================

import time
import threading

from campaign import Campaign


def run_deadline_checker(campaign: Campaign):
    """
    Runs a loop that monitors the campaign deadline and closes it.

    This function blocks until the deadline is reached, so it should be
    run in a background thread.

    Args
    ----
    campaign : Campaign
        The campaign object to monitor and close.

    Flow
    ----
      1. Sleep until the deadline (or until very close to it)
      2. Check the clock one final time
      3. If deadline passed, call close_campaign() to resolve status
      4. Log the outcome
    """
    time_until_deadline = campaign.deadline - time.time()

    if time_until_deadline > 0:
        print(f"\n[DEADLINE_CHECKER] Waiting {time_until_deadline:.1f}s for deadline...")
        time.sleep(time_until_deadline)
    else:
        print(f"\n[DEADLINE_CHECKER] Deadline already passed!")

    # Double-check that the deadline has actually elapsed (clock drift buffer)
    if time.time() >= campaign.deadline:
        close_campaign(campaign)
    else:
        # Rare race: deadline checker woke up just before deadline
        # Sleep a tiny bit more
        margin = campaign.deadline - time.time()
        if margin > 0:
            time.sleep(margin + 0.01)
        close_campaign(campaign)


def close_campaign(campaign: Campaign):
    """
    Resolves the campaign status after the deadline.

    Implements the all-or-nothing funding model:
      - If the observed total_pledged >= goal_amount, mark as "successful"
      - Otherwise, mark as "failed"
      - Set status to prevent new pledges (via is_live())

    Note: This uses the counter total_pledged, which may be corrupted by
    race conditions in the pledge engine. The verifier will show the
    discrepancy between this (corrupted) result and the true total.

    Args
    ----
    campaign : Campaign
        The campaign object to close.
    """
    campaign.status = "successful" if campaign.total_pledged >= campaign.goal_amount else "failed"

    print(f"\n[DEADLINE] Campaign '{campaign.title}' CLOSED at {time.strftime('%H:%M:%S')}")
    print(f"           Pledged: ${campaign.total_pledged:,.2f} / Goal: ${campaign.goal_amount:,.2f}")
    print(f"           Result: {campaign.status.upper()}")


def start_deadline_checker_thread(campaign: Campaign) -> threading.Thread:
    """
    Convenience helper to start the deadline checker in a daemon thread.

    Returns the thread object so the caller can join() if desired.

    Args
    ----
    campaign : Campaign
        The campaign to monitor.

    Returns
    -------
    threading.Thread
        A daemon thread running run_deadline_checker().
    """
    thread = threading.Thread(
        target=run_deadline_checker,
        args=(campaign,),
        daemon=True,
        name="DeadlineChecker",
    )
    thread.start()
    return thread
