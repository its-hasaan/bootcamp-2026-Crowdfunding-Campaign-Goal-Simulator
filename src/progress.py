# =============================================================================
# MODULE 3: Progress Reporter
# =============================================================================
# Provides real-time progress updates on campaign funding status.
# Reads the shared (potentially inconsistent) campaign state and formats it
# in a human-readable way for display to backers/admins.
#
# Note: This reads total_pledged and backer_count which may be corrupted by
# race conditions in the pledge engine, so the progress % may not match the
# true total in the append-only pledge log.
# =============================================================================

from campaign import Campaign


def get_progress(campaign: Campaign) -> str:
    """
    Returns a human-readable funding progress string.

    Format: "$X,XXX / $X,XXX — YY.Y% (N backers)"

    Args
    ----
    campaign : Campaign
        The campaign object to query.

    Returns
    -------
    str
        A formatted progress string showing:
        - total_pledged (as it appears in the counter, possibly corrupted)
        - goal_amount
        - percentage of goal reached
        - backer count

    Example
    -------
    >>> campaign = Campaign("Test", 10000, 60)
    >>> campaign.total_pledged = 6500
    >>> campaign.backer_count = 65
    >>> print(get_progress(campaign))
    $6,500.00 / $10,000.00 — 65.0% (65 backers)
    """
    if campaign.goal_amount <= 0:
        percentage = 0.0
    else:
        percentage = (campaign.total_pledged / campaign.goal_amount) * 100.0

    return (
        f"${campaign.total_pledged:>10,.2f} / ${campaign.goal_amount:>10,.2f} "
        f"— {percentage:>5.1f}% ({campaign.backer_count} backers)"
    )


def get_progress_detailed(campaign: Campaign) -> dict:
    """
    Returns progress as a dict for programmatic use (e.g. JSON API).

    Returns
    -------
    dict
        Contains:
        - 'total_pledged': float
        - 'goal_amount': float
        - 'percentage': float (0–100)
        - 'backer_count': int
        - 'status': str ("live", "successful", "failed")
        - 'is_live': bool (True if still accepting pledges)
    """
    percentage = (campaign.total_pledged / campaign.goal_amount * 100.0) if campaign.goal_amount else 0.0

    return {
        "total_pledged": campaign.total_pledged,
        "goal_amount": campaign.goal_amount,
        "percentage": percentage,
        "backer_count": campaign.backer_count,
        "status": campaign.status,
        "is_live": campaign.is_live(),
    }
