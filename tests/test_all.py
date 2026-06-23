import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
import pytest

from campaign import Campaign
from pledge_engine import pledge, pledge_log, get_true_total, get_true_backer_count
from progress import get_progress, get_progress_detailed
from deadline import close_campaign
from verifier import verify_results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh_campaign(goal=1000.0, duration=60):
    """Return a brand-new Campaign with a clean state."""
    return Campaign(title="Test Campaign", goal_amount=goal, duration_sec=duration)


def clear_log():
    """Clear the global pledge log between tests."""
    pledge_log.clear()


# ---------------------------------------------------------------------------
# MODULE 1: Campaign Model
# ---------------------------------------------------------------------------

class TestCampaign:

    def test_initial_status_is_live(self):
        c = fresh_campaign()
        assert c.status == "live"

    def test_initial_total_pledged_is_zero(self):
        c = fresh_campaign()
        assert c.total_pledged == 0.0

    def test_initial_backer_count_is_zero(self):
        c = fresh_campaign()
        assert c.backer_count == 0

    def test_is_live_returns_true_within_deadline(self):
        c = fresh_campaign(duration=60)
        assert c.is_live() is True

    def test_is_live_returns_false_after_deadline(self):
        c = fresh_campaign(duration=1)
        c.deadline = time.time() - 1   # force deadline in the past
        assert c.is_live() is False

    def test_is_live_returns_false_when_status_not_live(self):
        c = fresh_campaign()
        c.status = "failed"
        assert c.is_live() is False

    def test_repr_contains_title(self):
        c = fresh_campaign()
        assert "Test Campaign" in repr(c)


# ---------------------------------------------------------------------------
# MODULE 2: Pledge Engine
# ---------------------------------------------------------------------------

class TestPledgeEngine:

    def setup_method(self):
        clear_log()

    def test_pledge_accepted_when_live(self):
        c = fresh_campaign()
        result = pledge(c, "backer_001", 100.0)
        assert result is True

    def test_pledge_increments_backer_count(self):
        c = fresh_campaign()
        pledge(c, "backer_001", 100.0)
        assert c.backer_count == 1

    def test_pledge_appends_to_log(self):
        c = fresh_campaign()
        pledge(c, "backer_001", 100.0)
        assert len(pledge_log) == 1
        assert pledge_log[0]["backer_id"] == "backer_001"
        assert pledge_log[0]["amount"] == 100.0

    def test_pledge_rejected_after_deadline(self):
        c = fresh_campaign()
        c.deadline = time.time() - 1   # expire the campaign
        result = pledge(c, "backer_001", 100.0)
        assert result is False

    def test_pledge_rejected_when_status_not_live(self):
        c = fresh_campaign()
        c.status = "failed"
        result = pledge(c, "backer_001", 100.0)
        assert result is False

    def test_get_true_total_sums_log(self):
        c = fresh_campaign()
        pledge(c, "b1", 100.0)
        pledge(c, "b2", 200.0)
        assert get_true_total() == 300.0

    def test_get_true_backer_count(self):
        c = fresh_campaign()
        pledge(c, "b1", 100.0)
        pledge(c, "b2", 200.0)
        assert get_true_backer_count() == 2


# ---------------------------------------------------------------------------
# MODULE 3: Progress Reporter
# ---------------------------------------------------------------------------

class TestProgress:

    def test_get_progress_zero_percent(self):
        c = fresh_campaign(goal=1000.0)
        c.total_pledged = 0.0
        c.backer_count = 0
        result = get_progress(c)
        assert "0.0%" in result

    def test_get_progress_fifty_percent(self):
        c = fresh_campaign(goal=1000.0)
        c.total_pledged = 500.0
        c.backer_count = 5
        result = get_progress(c)
        assert "50.0%" in result

    def test_get_progress_hundred_percent(self):
        c = fresh_campaign(goal=1000.0)
        c.total_pledged = 1000.0
        c.backer_count = 10
        result = get_progress(c)
        assert "100.0%" in result

    def test_get_progress_detailed_keys(self):
        c = fresh_campaign(goal=1000.0)
        d = get_progress_detailed(c)
        assert "total_pledged" in d
        assert "goal_amount" in d
        assert "percentage" in d
        assert "backer_count" in d
        assert "status" in d
        assert "is_live" in d


# ---------------------------------------------------------------------------
# MODULE 4: Deadline Checker
# ---------------------------------------------------------------------------

class TestDeadline:

    def test_close_campaign_successful_when_goal_met(self):
        c = fresh_campaign(goal=1000.0)
        c.total_pledged = 1000.0
        close_campaign(c)
        assert c.status == "successful"

    def test_close_campaign_failed_when_goal_not_met(self):
        c = fresh_campaign(goal=1000.0)
        c.total_pledged = 500.0
        close_campaign(c)
        assert c.status == "failed"

    def test_close_campaign_exactly_at_goal(self):
        c = fresh_campaign(goal=1000.0)
        c.total_pledged = 1000.0
        close_campaign(c)
        assert c.status == "successful"


# ---------------------------------------------------------------------------
# MODULE 6: Verifier — Race Condition Detection
# ---------------------------------------------------------------------------

class TestVerifier:

    def setup_method(self):
        clear_log()

    def test_verifier_detects_no_race_when_totals_match(self):
        c = fresh_campaign(goal=300.0)
        pledge(c, "b1", 100.0)
        pledge(c, "b2", 100.0)
        pledge(c, "b3", 100.0)
        # force the counter to match the log (no race simulation)
        c.total_pledged = get_true_total()
        close_campaign(c)
        result = verify_results(c)
        assert result["has_race_condition"] is False

    def test_verifier_detects_race_when_totals_differ(self):
        c = fresh_campaign(goal=300.0)
        pledge(c, "b1", 100.0)
        pledge(c, "b2", 100.0)
        pledge(c, "b3", 100.0)
        # simulate corrupted counter (race condition lost $200)
        c.total_pledged = 100.0
        close_campaign(c)
        result = verify_results(c)
        assert result["has_race_condition"] is True
        assert result["lost"] == pytest.approx(200.0)

    def test_verifier_detects_verdict_mismatch(self):
        c = fresh_campaign(goal=300.0)
        pledge(c, "b1", 100.0)
        pledge(c, "b2", 100.0)
        pledge(c, "b3", 100.0)
        # race condition makes counter show only $100 — campaign declared failed
        c.total_pledged = 100.0
        close_campaign(c)   # will mark "failed" because 100 < 300
        result = verify_results(c)
        assert result["verdict_mismatch"] is True
        assert result["observed_verdict"] == "failed"
        assert result["true_verdict"] == "successful"
