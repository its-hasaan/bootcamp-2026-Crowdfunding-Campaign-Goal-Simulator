# =============================================================================
# Temporal Workflow: Campaign Workflow
# =============================================================================
# Replaces the thread-based producer-consumer queue pattern with a Temporal
# Workflow.  Temporal guarantees that workflow code is single-threaded, so
# signals (pledges) are processed one at a time — race conditions are
# impossible by construction.
#
# Concepts mapping:
#   queue.Queue + _queue_worker  →  @workflow.signal (pledge_signal)
#   DeadlineChecker thread       →  workflow.sleep(duration)
#   get_progress() / verify()    →  @workflow.query
# =============================================================================

from datetime import timedelta
from dataclasses import dataclass, field
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal_app.activities import (
        log_pledge_activity,
        log_campaign_result_activity,
    )


# ---------------------------------------------------------------------------
# Data classes for workflow input and pledge records
# ---------------------------------------------------------------------------
@dataclass
class CampaignInput:
    """Input parameters to start a campaign workflow."""
    title: str
    goal_amount: float
    duration_sec: int
    num_backers: int
    pledge_amount: float


@dataclass
class PledgeData:
    """Data sent with a pledge signal."""
    backer_id: str
    amount: float


# ---------------------------------------------------------------------------
# Workflow Definition
# ---------------------------------------------------------------------------
@workflow.defn
class CampaignWorkflow:
    """
    A Temporal Workflow representing a crowdfunding campaign lifecycle.

    The workflow:
      1. Initialises campaign state from CampaignInput.
      2. Accepts pledge signals while the campaign is live.
      3. Sleeps until the campaign deadline (replaces DeadlineChecker thread).
      4. Resolves campaign status (successful / failed).
      5. Exposes progress and result queries for external callers.

    Because Temporal executes workflow code on a single thread with
    deterministic replay, there is ZERO risk of race conditions on
    the shared mutable state (total_pledged, backer_count, etc.).
    """

    # ---- internal state (replaces Campaign class fields) ----
    def __init__(self) -> None:
        self._title: str = ""
        self._goal_amount: float = 0.0
        self._duration_sec: int = 0
        self._total_pledged: float = 0.0
        self._backer_count: int = 0
        self._status: str = "live"
        self._pledge_log: list[dict] = []
        self._campaign_closed: bool = False

    # -----------------------------------------------------------------
    # Main run method — the campaign lifecycle
    # -----------------------------------------------------------------
    @workflow.run
    async def run(self, campaign_input: CampaignInput) -> dict:
        """
        Entry point for the workflow execution.

        1. Store campaign parameters.
        2. Sleep for the campaign duration (acts as the deadline timer).
        3. Close the campaign and resolve status.
        4. Return the final verification result.
        """
        # Initialise state from input
        self._title = campaign_input.title
        self._goal_amount = campaign_input.goal_amount
        self._duration_sec = campaign_input.duration_sec

        workflow.logger.info(
            f"Campaign '{self._title}' started — "
            f"goal=${self._goal_amount:,.2f}, duration={self._duration_sec}s"
        )

        # --- Wait for the deadline (replaces DeadlineChecker thread) ---
        # During this sleep, pledge signals are still processed.
        await workflow.sleep(timedelta(seconds=self._duration_sec))

        # --- Close campaign ---
        self._campaign_closed = True
        if self._total_pledged >= self._goal_amount:
            self._status = "successful"
        else:
            self._status = "failed"

        workflow.logger.info(
            f"Campaign '{self._title}' CLOSED — "
            f"status={self._status.upper()}, "
            f"pledged=${self._total_pledged:,.2f}"
        )

        # Execute the logging activity (side-effect → must be in an activity)
        result = self._build_result()
        await workflow.execute_activity(
            log_campaign_result_activity,
            result,
            start_to_close_timeout=timedelta(seconds=10),
        )

        return result

    # -----------------------------------------------------------------
    # Signal: Accept a pledge
    # -----------------------------------------------------------------
    @workflow.signal
    async def pledge_signal(self, pledge: PledgeData) -> None:
        """
        Receives a pledge from a backer.

        Because Temporal processes signals sequentially on the workflow
        thread, there is no concurrent access to _total_pledged or
        _backer_count — race conditions are eliminated by design.
        """
        if self._campaign_closed or self._status != "live":
            workflow.logger.info(
                f"[REJECTED] Backer {pledge.backer_id} — campaign is not live"
            )
            return

        # Serialised state update — no locks needed
        self._total_pledged += pledge.amount
        self._backer_count += 1
        self._pledge_log.append({
            "backer_id": pledge.backer_id,
            "amount": pledge.amount,
            "observed_total": self._total_pledged,
        })

        # Fire-and-forget activity for console output
        await workflow.execute_activity(
            log_pledge_activity,
            {
                "backer_id": pledge.backer_id,
                "amount": pledge.amount,
                "total": self._total_pledged,
            },
            start_to_close_timeout=timedelta(seconds=5),
        )

    # -----------------------------------------------------------------
    # Query: Get live progress
    # -----------------------------------------------------------------
    @workflow.query
    def get_progress(self) -> dict:
        """Returns current campaign progress (queryable while workflow runs)."""
        pct = (
            (self._total_pledged / self._goal_amount * 100.0)
            if self._goal_amount > 0 else 0.0
        )
        return {
            "title": self._title,
            "total_pledged": self._total_pledged,
            "goal_amount": self._goal_amount,
            "percentage": round(pct, 2),
            "backer_count": self._backer_count,
            "status": self._status,
        }

    # -----------------------------------------------------------------
    # Query: Get final verification result
    # -----------------------------------------------------------------
    @workflow.query
    def get_result(self) -> dict:
        """Returns the full verification result (best called after completion)."""
        return self._build_result()

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------
    def _build_result(self) -> dict:
        """Assembles the verification result dict (mirrors verifier.py output)."""
        observed = self._total_pledged
        expected = sum(e["amount"] for e in self._pledge_log)
        real_backers = len(self._pledge_log)

        lost = expected - observed
        lost_pct = (lost / expected * 100) if expected > 0 else 0.0
        true_verdict = "successful" if expected >= self._goal_amount else "failed"

        return {
            "title": self._title,
            "observed": observed,
            "expected": expected,
            "lost": lost,
            "lost_percentage": lost_pct,
            "real_backers": real_backers,
            "observed_backer_count": self._backer_count,
            "observed_verdict": self._status,
            "true_verdict": true_verdict,
            "verdict_mismatch": true_verdict != self._status,
            "has_race_condition": lost > 0,
            "goal_amount": self._goal_amount,
            "pledge_log_length": len(self._pledge_log),
        }
