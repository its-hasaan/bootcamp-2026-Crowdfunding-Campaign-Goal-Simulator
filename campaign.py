# =============================================================================
# MODULE 1: Campaign Model
# =============================================================================
# Holds the shared mutable state of a crowdfunding campaign.
# All fields are plain Python variables — NO locks, NO thread-safety.
# This is intentional: we want to demonstrate what happens when multiple
# threads read and write these values at the same time (race conditions).
# =============================================================================

import time


class Campaign:
    """
    Represents a single crowdfunding campaign.

    Fields
    ------
    title        : Human-readable name of the campaign.
    goal_amount  : The funding target (e.g. 10000 for $10,000).
    duration_sec : How long the campaign stays live, in seconds.
    deadline     : Absolute Unix timestamp when the campaign closes.
    total_pledged: Running sum of all pledges — shared, unprotected.
    backer_count : Number of backers who pledged — shared, unprotected.
    status       : "live" → "successful" or "failed" after deadline.
    """

    def __init__(self, title: str, goal_amount: float, duration_sec: int):
        # --- Campaign identity ---
        self.title = title

        # --- Funding goal ---
        self.goal_amount = goal_amount          # e.g. 10000.0

        # --- Timing ---
        self.duration_sec = duration_sec
        self.deadline = time.time() + duration_sec  # absolute end time

        # --- Shared mutable state (NO locking — race conditions live here) ---
        self.total_pledged = 0.0    # incremented by concurrent pledge() calls
        self.backer_count  = 0      # incremented alongside total_pledged

        # --- Campaign lifecycle ---
        self.status = "live"        # transitions to "successful" or "failed"

    def is_live(self) -> bool:
        """Returns True only when the campaign is still accepting pledges."""
        return self.status == "live" and time.time() < self.deadline

    def __repr__(self):
        return (
            f"Campaign(title={self.title!r}, goal=${self.goal_amount:,.2f}, "
            f"status={self.status!r}, pledged=${self.total_pledged:,.2f})"
        )
