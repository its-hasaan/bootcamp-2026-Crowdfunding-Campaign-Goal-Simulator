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
import queue

from campaign import Campaign


# ---------------------------------------------------------------------------
# Request classes for thread synchronization via Queue
# ---------------------------------------------------------------------------
class PledgeRequest:
    def __init__(self, campaign: Campaign, backer_id: str, amount: float, verbose: bool):
        self.campaign = campaign
        self.backer_id = backer_id
        self.amount = amount
        self.verbose = verbose
        self.event = threading.Event()
        self.success = False


class CloseRequest:
    def __init__(self, campaign: Campaign):
        self.campaign = campaign
        self.event = threading.Event()


# ---------------------------------------------------------------------------
# Global thread-safe queue and worker lifecycle management
# ---------------------------------------------------------------------------
pledge_queue: queue.Queue = queue.Queue()
_worker_thread = None
_worker_lock = threading.Lock()


def _queue_worker():
    while True:
        request = pledge_queue.get()
        if request is None:
            pledge_queue.task_done()
            break
        try:
            if isinstance(request, PledgeRequest):
                campaign = request.campaign
                if not campaign.is_live():
                    request.success = False
                    if request.verbose:
                        try:
                            print(f"  [REJECTED] Backer {request.backer_id} pledged ${request.amount:.2f} "
                                  f"- campaign is not live (status={campaign.status!r})")
                        except Exception:
                            pass
                else:
                    # Thread-safe read, add, write operations since only this thread runs them
                    current_total = campaign.total_pledged
                    new_total = current_total + request.amount
                    campaign.total_pledged = new_total
                    campaign.backer_count += 1
                    # Record the pledge on the campaign instance ledger (Change #1)
                    campaign.record_pledge(request.backer_id, request.amount, new_total)

                    request.success = True

                    if request.verbose:
                        try:
                            print(f"  [PLEDGE] Backer {request.backer_id:>6} pledged ${request.amount:>8.2f} "
                                  f"-> observed total ${new_total:>10.2f}")
                        except Exception:
                            pass
            elif isinstance(request, CloseRequest):
                campaign = request.campaign
                campaign.status = "successful" if campaign.total_pledged >= campaign.goal_amount else "failed"
        except Exception:
            pass
        finally:
            request.event.set()
            pledge_queue.task_done()


def _ensure_worker_started():
    global _worker_thread
    with _worker_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = threading.Thread(target=_queue_worker, daemon=True, name="PledgeQueueWorker")
            _worker_thread.start()


def pledge(campaign: Campaign, backer_id: str, amount: float,
           verbose: bool = True) -> bool:
    """
    Attempt to add a pledge to the campaign.

    Returns True if the pledge was accepted, False if rejected.
    Set verbose=False to suppress per-pledge print output (used by demo.py).
    """
    _ensure_worker_started()
    request = PledgeRequest(campaign, backer_id, amount, verbose)
    pledge_queue.put(request)
    request.event.wait()
    return request.success


def enqueue_close_request(campaign: Campaign):
    """
    Safely resolves the campaign status through the queue.
    """
    _ensure_worker_started()
    request = CloseRequest(campaign)
    pledge_queue.put(request)
    request.event.wait()


def get_true_total(campaign: Campaign) -> float:
    """
    Compute the correct total by summing every recorded pledge in the campaign's ledger.
    This is the number the campaign SHOULD show if there were no race.
    """
    return sum(entry["amount"] for entry in campaign.pledge_log)


def get_true_backer_count(campaign: Campaign) -> int:
    """Returns the real number of successful pledges from the campaign's ledger."""
    return len(campaign.pledge_log)
