# =============================================================================
# MODULE 2: Pledge Engine  (intentional race condition)
# =============================================================================
# This module implements the naive pledge operation:
#
#   READ  total_pledged          ← snapshot may already be stale
#   ADD   amount
#   WRITE total_pledged = result ← silently overwrites concurrent writes
#
# When 50-100 threads run this simultaneously, multiple threads can read
# the SAME old value, each add their own amount, and each write back a
# partial total.  The result: lost updates.
#
# A separate append-only pledge log captures every pledge independently so
# we can compute the TRUE total and expose the discrepancy at the end.
# =============================================================================

import time
import threading

from campaign import Campaign


# ---------------------------------------------------------------------------
# Append-only pledge log — written to by every successful pledge call.
# Stored as a list of dicts; never modified after append.
# This is our "ground truth" to compare against campaign.total_pledged later.
# ---------------------------------------------------------------------------
pledge_log: list[dict] = []

# A plain (non-reentrant, non-locked) list append is thread-safe in CPython
# due to the GIL, so the log itself won't lose entries — only the shared
# counter arithmetic will race.
_log_lock = threading.Lock()   # used ONLY for the log list, NOT for the counter


def pledge(campaign: Campaign, backer_id: str, amount: float,
           verbose: bool = True) -> bool:
    """
    Attempt to add a pledge to the campaign.

    Returns True if the pledge was accepted, False if rejected.
    Set verbose=False to suppress per-pledge print output (used by demo.py).

    *** The update to total_pledged and backer_count is intentionally
        NOT atomic — this is where the race condition occurs. ***
    """

    # --- Guard: reject pledges when the campaign is no longer live ---
    if not campaign.is_live():
        if verbose:
            print(f"  [REJECTED] Backer {backer_id} pledged ${amount:.2f} "
                  f"— campaign is not live (status={campaign.status!r})")
        return False

    # -------------------------------------------------------------------------
    # THE RACE CONDITION
    # -------------------------------------------------------------------------
    # Step 1 — READ: take a local snapshot of the current total
    current_total = campaign.total_pledged      # ← Thread A reads 500
                                                # ← Thread B also reads 500 (same!)

    # Simulate a tiny bit of real work / network latency so threads overlap
    time.sleep(0.001)

    # Step 2 — ADD: compute new total locally
    new_total = current_total + amount          # A computes 600, B computes 700

    # Step 3 — WRITE: store result back (NO lock)
    campaign.total_pledged = new_total          # A writes 600 … then B writes 700
                                                # A's update is lost → only +200 instead of +300
    campaign.backer_count += 1                  # also racy, but less visible here
    # -------------------------------------------------------------------------

    # --- Append to the ground-truth log (protected only to avoid list corruption) ---
    with _log_lock:
        pledge_log.append({
            "backer_id":      backer_id,
            "amount":         amount,
            "observed_total": new_total,        # the total THIS thread saw after writing
            "timestamp":      time.time(),
        })

    if verbose:
        print(f"  [PLEDGE] Backer {backer_id:>6} pledged ${amount:>8.2f} "
              f"→ observed total ${new_total:>10.2f}")

    return True


def get_true_total() -> float:
    """
    Compute the correct total by summing every recorded pledge.
    This is the number the campaign SHOULD show if there were no race.
    """
    return sum(entry["amount"] for entry in pledge_log)


def get_true_backer_count() -> int:
    """Returns the real number of successful pledges from the log."""
    return len(pledge_log)
