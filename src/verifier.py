# =============================================================================
# MODULE 6: Race Condition Verifier
# =============================================================================
# Detects and reports data loss caused by race conditions in the pledge engine.
#
# Compares two totals:
#   1. campaign.total_pledged — the corrupted counter (affected by races)
#   2. sum(pledge_log)        — the ground truth (every pledge recorded)
#
# If they don't match, pledges were silently lost. If the campaign result
# contradicts the true total, that's a critical correctness failure.
# =============================================================================

from campaign      import Campaign
from pledge_engine import get_true_total, get_true_backer_count


def verify_results(campaign: Campaign) -> dict:
    """
    Detects and reports race condition failures.

    Compares the observed (potentially corrupted) campaign total against
    the ground truth from the pledge log, and checks for verdict inversions
    (declared failed when should be successful, or vice versa).

    Args
    ----
    campaign : Campaign
        The completed campaign to verify.

    Returns
    -------
    dict
        Contains:
        - 'observed': float (campaign.total_pledged)
        - 'expected': float (sum of pledge log)
        - 'lost': float (difference)
        - 'lost_percentage': float (% of expected lost)
        - 'real_backers': int (true backer count)
        - 'observed_verdict': str ("successful" or "failed")
        - 'true_verdict': str ("successful" or "failed")
        - 'verdict_mismatch': bool (True if observed != true)
        - 'has_race_condition': bool (True if lost > 0)
    """
    observed = campaign.total_pledged
    expected = get_true_total()
    real_backers = get_true_backer_count()

    lost = expected - observed
    lost_pct = (lost / expected * 100) if expected > 0 else 0

    # Determine verdicts
    true_verdict = "successful" if expected >= campaign.goal_amount else "failed"
    observed_verdict = campaign.status  # should match status set by deadline_checker

    verdict_mismatch = (true_verdict != observed_verdict)
    has_race = lost > 0

    result = {
        "observed": observed,
        "expected": expected,
        "lost": lost,
        "lost_percentage": lost_pct,
        "real_backers": real_backers,
        "observed_backer_count": campaign.backer_count,
        "observed_verdict": observed_verdict,
        "true_verdict": true_verdict,
        "verdict_mismatch": verdict_mismatch,
        "has_race_condition": has_race,
    }

    # Print the report
    print("\n" + "=" * 70)
    print("  RACE CONDITION ANALYSIS REPORT")
    print("=" * 70)

    print("\n  Pledge Totals:")
    print(f"    Real pledges (log)        : ${expected:>12,.2f}")
    print(f"    Observed (counter)        : ${observed:>12,.2f}")
    print(f"    Lost to race conditions   : ${lost:>12,.2f}")

    if expected > 0:
        print(f"    Loss percentage           : {lost_pct:>13.2f}%")

    print("\n  Backer Counts:")
    print(f"    Real backers (log)        : {real_backers:>12}")
    print(f"    Observed (counter)        : {campaign.backer_count:>12}")
    print(f"    Lost backer count         : {real_backers - campaign.backer_count:>12}")

    print("\n  Campaign Verdict:")
    print(f"    Goal amount               : ${campaign.goal_amount:>12,.2f}")
    print(f"    True verdict              : {true_verdict.upper():>12}")
    print(f"    Observed verdict          : {observed_verdict.upper():>12}")

    if has_race:
        print(f"\n  *** RACE CONDITIONS DETECTED ***")
        print(f"  {lost_pct:.2f}% of pledges were silently lost!")

    if verdict_mismatch:
        print(f"\n  *** CORRECTNESS FAILURE ***")
        if true_verdict == "successful" and observed_verdict == "failed":
            print(f"  Campaign was declared FAILED, but the real pledges MET the goal!")
            print(f"  {real_backers} real backers were betrayed by race conditions.")
        else:
            print(f"  Campaign verdict mismatch: true={true_verdict}, observed={observed_verdict}")

    if not has_race and not verdict_mismatch:
        print(f"\n  ✓ No race conditions detected in this run.")
        print(f"  (Race conditions are non-deterministic; run again to try to trigger.)")

    print("=" * 70 + "\n")

    return result


def print_summary(campaign: Campaign, load_result: dict):
    """
    Prints a summary combining load simulation stats and verification.

    Args
    ----
    campaign : Campaign
        The completed campaign.
    load_result : dict
        Result dict from load_simulator.run().
    """
    print("\n" + "=" * 70)
    print("  SIMULATION SUMMARY")
    print("=" * 70)

    print(f"\n  Load Simulator:")
    print(f"    Threads spawned           : {load_result['num_threads']}")
    print(f"    Pledges accepted          : {load_result['num_successful']}")
    print(f"    Pledges rejected          : {load_result['num_failed']}")
    print(f"    Simulation time           : {load_result['elapsed_time']:.3f}s")
    print(f"    Expected total            : ${load_result['expected_total']:,.2f}")

    print(f"\n  Campaign Results:")
    print(f"    Campaign title            : {campaign.title}")
    print(f"    Campaign status           : {campaign.status.upper()}")
    print(f"    Observed total            : ${campaign.total_pledged:,.2f}")

    verify_results(campaign)
