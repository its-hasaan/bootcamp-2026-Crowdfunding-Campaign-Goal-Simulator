# =============================================================================
# Temporal Activities: Side-Effect Operations
# =============================================================================
# Activities handle non-deterministic or side-effect operations that cannot
# live inside a Temporal Workflow (which must be deterministic for replay).
#
# In our case, the main side effects are console output (print statements).
# =============================================================================

from temporalio import activity


@activity.defn
async def log_pledge_activity(data: dict) -> None:
    """
    Logs a successful pledge to the console.

    This is an Activity because printing to stdout is a side effect.
    Temporal workflows must be deterministic, so I/O belongs here.

    Args
    ----
    data : dict
        Contains 'backer_id', 'amount', and 'total'.
    """
    print(
        f"  [PLEDGE] Backer {data['backer_id']:>6} pledged "
        f"${data['amount']:>8.2f} -> observed total ${data['total']:>10.2f}"
    )


@activity.defn
async def log_campaign_result_activity(result: dict) -> None:
    """
    Prints the final campaign verification report.

    Mirrors the output of the original verifier.py module but runs as
    a Temporal Activity for side-effect safety.

    Args
    ----
    result : dict
        The verification result dict from CampaignWorkflow._build_result().
    """
    observed = result["observed"]
    expected = result["expected"]
    lost = result["lost"]
    lost_pct = result["lost_percentage"]
    real_backers = result["real_backers"]
    observed_backer_count = result["observed_backer_count"]
    goal_amount = result["goal_amount"]
    true_verdict = result["true_verdict"]
    observed_verdict = result["observed_verdict"]
    has_race = result["has_race_condition"]
    verdict_mismatch = result["verdict_mismatch"]

    print("\n" + "=" * 70)
    print("  TEMPORAL WORKFLOW — CAMPAIGN RESULT REPORT")
    print("=" * 70)

    print(f"\n  Campaign: {result['title']}")

    print("\n  Pledge Totals:")
    print(f"    Real pledges (log)        : ${expected:>12,.2f}")
    print(f"    Observed (counter)        : ${observed:>12,.2f}")
    print(f"    Lost to race conditions   : ${lost:>12,.2f}")

    if expected > 0:
        print(f"    Loss percentage           : {lost_pct:>13.2f}%")

    print("\n  Backer Counts:")
    print(f"    Real backers (log)        : {real_backers:>12}")
    print(f"    Observed (counter)        : {observed_backer_count:>12}")
    print(f"    Lost backer count         : {real_backers - observed_backer_count:>12}")

    print("\n  Campaign Verdict:")
    print(f"    Goal amount               : ${goal_amount:>12,.2f}")
    print(f"    True verdict              : {true_verdict.upper():>12}")
    print(f"    Observed verdict          : {observed_verdict.upper():>12}")

    if has_race:
        print(f"\n  *** RACE CONDITIONS DETECTED ***")
        print(f"  {lost_pct:.2f}% of pledges were silently lost!")
    elif not verdict_mismatch:
        print(f"\n  [OK] No race conditions detected -- Temporal guarantees it!")
        print(f"  All {real_backers} pledges processed with perfect consistency.")

    if verdict_mismatch:
        print(f"\n  *** CORRECTNESS FAILURE ***")
        print(f"  Verdict mismatch: true={true_verdict}, observed={observed_verdict}")

    print("=" * 70 + "\n")
