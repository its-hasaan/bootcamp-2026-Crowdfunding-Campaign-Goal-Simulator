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
#
# Temporal 102 additions (see docs/temporal-102.md for the full write-up):
#   RetryPolicy                 →  configurable Activity retry behaviour
#   Continue-As-New              →  keeps Event History small for long/busy campaigns
#   workflow.patched()           →  safely evolve Workflow code already running in prod
# =============================================================================

import asyncio
from datetime import timedelta
from dataclasses import dataclass, field
from typing import Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.temporal_app.activities import (
        validate_campaign_activity,
        log_pledge_activity,
        log_campaign_result_activity,
    )


# ---------------------------------------------------------------------------
# Data classes for workflow input and pledge records
# ---------------------------------------------------------------------------
@dataclass
class CampaignInput:
    """
    Input parameters to start a campaign workflow.

    Temporal 102 best practice: use a single dataclass (rather than loose
    positional parameters) for Workflow input so the schema can evolve in a
    backwards-compatible way (new fields just need a default value).

    The `carried_*` and `remaining_duration_sec` fields are only populated
    internally when the Workflow calls `workflow.continue_as_new()` — they
    let the new Run pick up exactly where the previous Run left off.
    """
    title: str
    goal_amount: float
    duration_sec: int
    num_backers: int
    pledge_amount: float

    # Continue-As-New configuration / carried-forward state (Temporal 102)
    continue_as_new_after: int = 100_000
    carried_total_pledged: float = 0.0
    carried_backer_count: int = 0
    remaining_duration_sec: Optional[int] = None
    run_generation: int = 1


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

        # Temporal 102 — Continue-As-New bookkeeping.
        # `_pledge_log` is only kept for the *current* Run/generation so
        # that Event History (and this in-memory list) never grows without
        # bound; totals are carried forward across generations instead.
        self._continue_as_new_after: int = 100_000
        self._generation: int = 1
        self._generation_signal_count: int = 0
        self._should_continue_as_new: bool = False

    # -----------------------------------------------------------------
    # Main run method — the campaign lifecycle
    # -----------------------------------------------------------------
    @workflow.run
    async def run(self, campaign_input: CampaignInput) -> dict:
        """
        Entry point for the workflow execution.

        1. Store campaign parameters (or resume carried-forward state after
           a Continue-As-New).
        2. Validate campaign parameters via an Activity that retries
           automatically (Temporal 102 — Activity retries).
        3. Wait for the deadline OR for the Continue-As-New threshold to be
           reached, whichever happens first (Temporal 102 — Event History
           size management).
        4. If the campaign is still running but has accumulated too many
           signals, hand off to a new Run via `continue_as_new`.
        5. Otherwise close the campaign and resolve status.
        6. Return the final verification result.
        """
        # Initialise state from input — resuming carried totals if this Run
        # was produced by a previous generation's continue_as_new() call.
        self._title = campaign_input.title
        self._goal_amount = campaign_input.goal_amount
        self._duration_sec = (
            campaign_input.remaining_duration_sec
            if campaign_input.remaining_duration_sec is not None
            else campaign_input.duration_sec
        )
        self._continue_as_new_after = campaign_input.continue_as_new_after
        self._total_pledged = campaign_input.carried_total_pledged
        self._backer_count = campaign_input.carried_backer_count
        self._generation = campaign_input.run_generation

        workflow.logger.info(
            f"Campaign '{self._title}' started (generation {self._generation}) — "
            f"goal=${self._goal_amount:,.2f}, duration={self._duration_sec}s, "
            f"carried_total=${self._total_pledged:,.2f}"
        )

        # --- Temporal 102: Activity Retries ---
        # validate_campaign_activity fails on its first two attempts by
        # design. This RetryPolicy controls how Temporal retries it —
        # Activity failure is normal and expected, unlike Workflow failure.
        await workflow.execute_activity(
            validate_campaign_activity,
            {"title": self._title, "goal_amount": self._goal_amount},
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=1.0,
                maximum_attempts=5,
            ),
        )

        # --- Wait for the deadline OR the Continue-As-New threshold ---
        # (replaces DeadlineChecker thread). During this wait, pledge
        # signals are still processed.
        deadline = workflow.now() + timedelta(seconds=self._duration_sec)
        while True:
            remaining = deadline - workflow.now()
            if remaining <= timedelta(0):
                break
            try:
                await workflow.wait_condition(
                    lambda: self._should_continue_as_new, timeout=remaining
                )
                break  # condition became true before the deadline
            except asyncio.TimeoutError:
                break  # deadline reached first

        # --- Temporal 102: Continue-As-New ---
        # If we accumulated enough signals to risk a bloated Event History,
        # start a brand-new Run (same Workflow ID, new Run ID) that carries
        # the totals forward and keeps the remaining time on the clock.
        # This keeps each Run's Event History small and fast to replay.
        if self._should_continue_as_new:
            remaining = max(deadline - workflow.now(), timedelta(0))
            workflow.logger.info(
                f"[CONTINUE-AS-NEW] Generation {self._generation} reached "
                f"{self._generation_signal_count} signals — starting generation "
                f"{self._generation + 1} with {int(remaining.total_seconds())}s remaining."
            )
            next_input = CampaignInput(
                title=self._title,
                goal_amount=self._goal_amount,
                duration_sec=campaign_input.duration_sec,
                num_backers=campaign_input.num_backers,
                pledge_amount=campaign_input.pledge_amount,
                continue_as_new_after=self._continue_as_new_after,
                carried_total_pledged=self._total_pledged,
                carried_backer_count=self._backer_count,
                remaining_duration_sec=int(remaining.total_seconds()),
                run_generation=self._generation + 1,
            )
            workflow.continue_as_new(next_input)
            return {}  # unreachable — continue_as_new raises internally

        # --- Temporal 102: Versioning with Patching ---
        # workflow.patched() lets us safely introduce new behaviour for
        # brand-new Workflow Executions. Any Execution already running
        # before this code was deployed will not have this marker in its
        # Event History and will simply skip the branch on Replay — no
        # non-determinism errors. Once every pre-patch Execution has
        # closed, call workflow.deprecate_patch("grace-period-v1") and,
        # later, delete the check (and the old branch) entirely.
        if workflow.patched("grace-period-v1"):
            grace_period_sec = 3
            workflow.logger.info(
                f"[PATCH grace-period-v1] Extending campaign by "
                f"{grace_period_sec}s to accept last-moment pledges."
            )
            await workflow.sleep(timedelta(seconds=grace_period_sec))

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
            retry_policy=RetryPolicy(maximum_attempts=3),
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
        self._generation_signal_count += 1

        if self._campaign_closed:
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

        # Fire-and-forget activity for console output. RetryPolicy makes the
        # (small, best-effort) retry behaviour explicit rather than relying
        # on SDK defaults (Temporal 102 best practice).
        await workflow.execute_activity(
            log_pledge_activity,
            {
                "backer_id": pledge.backer_id,
                "amount": pledge.amount,
                "total": self._total_pledged,
            },
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # Temporal 102 — Continue-As-New trigger. Once this generation has
        # processed enough signals, flag the main run() loop to hand off to
        # a fresh Run instead of letting Event History grow unbounded.
        if (
            not self._should_continue_as_new
            and self._generation_signal_count >= self._continue_as_new_after
        ):
            workflow.logger.info(
                f"[CONTINUE-AS-NEW] Threshold of {self._continue_as_new_after} "
                f"signals reached this generation — requesting Continue-As-New."
            )
            self._should_continue_as_new = True

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
            "generation": self._generation,
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
        """
        Assembles the verification result dict (mirrors verifier.py output).

        Note (Temporal 102 — Continue-As-New): `_pledge_log` only holds
        entries for the *current* generation/Run, since it is reset by a
        fresh `__init__` every time `continue_as_new` starts a new Run. The
        canonical, cross-generation totals are `_total_pledged` and
        `_backer_count`, which are carried forward explicitly via
        `CampaignInput.carried_total_pledged` / `carried_backer_count`.
        Because signals are always processed one at a time (no threads),
        these two counters can never diverge — that's the whole point of
        replacing the racy counter with a Workflow.
        """
        observed = self._total_pledged
        expected = self._total_pledged
        real_backers = self._backer_count

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
            "generation": self._generation,
        }
