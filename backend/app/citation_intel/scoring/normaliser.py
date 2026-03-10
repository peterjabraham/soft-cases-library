"""
Batch normaliser for citation signals.

Min-max normalises citation_velocity and influential_citations
within a batch of results so they become 0-1 inputs to the
scoring formulas.

Called once per pipeline run on the full set of non-duplicate results.
Mutates records in-place and returns the list.
"""

from __future__ import annotations

from typing import Optional

from app.citation_intel.pipeline.raw_result import RawResultData


def _minmax(value: float, min_v: float, max_v: float) -> float:
    """Min-max normalise. Returns 0.5 if all values are identical."""
    if max_v == min_v:
        return 0.5
    return (value - min_v) / (max_v - min_v)


def normalise_citation_signals(results: list[RawResultData]) -> list[RawResultData]:
    """
    Normalise citation_velocity and influential_citations to 0–1 within the batch.

    Only considers non-duplicate results with citation data (SS only).
    Stores normalised values back onto result as:
      result._velocity_norm — used by scorer
      result._influential_norm — used by scorer

    Preprint/web results without citation data get 0.0 for both.
    """
    # Filter to results with citation data
    ss_results = [r for r in results if not r.is_duplicate and r.citation_count is not None]

    # Compute citation velocities
    velocities = [_citation_velocity(r) for r in ss_results]
    influentials = [float(r.influential_citations or 0) for r in ss_results]

    v_min, v_max = (min(velocities), max(velocities)) if velocities else (0.0, 0.0)
    i_min, i_max = (min(influentials), max(influentials)) if influentials else (0.0, 0.0)

    # Build lookup from result id → normalised scores
    for r, vel, inf in zip(ss_results, velocities, influentials):
        r.citation_velocity = vel
        r._velocity_norm = _minmax(vel, v_min, v_max)
        r._influential_norm = _minmax(inf, i_min, i_max)

    # Non-SS results keep their PrivateAttr defaults (0.0)

    return results


def _citation_velocity(r: RawResultData) -> float:
    """
    Citations per month using recent_citations (last 12 months) ÷ paper age.

    Falls back to total citation_count ÷ age if recent not available.
    Returns 0.0 if age is 0 or no citation data.
    """
    if r.citation_count is None:
        return 0.0

    age_months = _age_months(r.published_date)
    if age_months == 0:
        return 0.0

    if r.recent_citations is not None:
        return round(r.recent_citations / age_months, 4)

    return round((r.citation_count or 0) / age_months, 4)


def _age_months(published_date: Optional[str]) -> int:
    """
    Calculate paper age in months from published_date string.

    Accepts: "YYYY", "YYYY-MM", "YYYY-MM-DD".
    Returns 0 if unparseable.
    """
    if not published_date:
        return 0
    from datetime import date

    today = date.today()
    try:
        parts = published_date.strip().split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        pub = date(year, month, 1)
        delta_months = (today.year - pub.year) * 12 + (today.month - pub.month)
        return max(delta_months, 0)
    except (ValueError, IndexError):
        return 0
