"""
Post-scoring filter gate.

Applies the user-configured min_topical_relevance from filter_config.
This is a stricter gate than the pipeline's hardcoded RELEVANCE_GATE (0.25).

Called once per pipeline run after scoring, before storing CIScoredResult rows.
"""

from __future__ import annotations

from typing import Optional

from app.citation_intel.pipeline.raw_result import RawResultData


def apply_filter_config_gate(
    results: list[RawResultData],
    min_topical_relevance: Optional[float],
) -> None:
    """
    Exclude results whose topical_relevance is below the user's requested gate.

    Rules:
    - No-op if min_topical_relevance is None or <= 0.0
    - Already-excluded results are skipped (reason is not overwritten)
    - Mutates results in-place; returns None
    """
    if not min_topical_relevance or min_topical_relevance <= 0.0:
        return

    for r in results:
        if r.excluded:
            continue
        rel = r.topical_relevance or 0.0
        if rel < min_topical_relevance:
            r.excluded = True
            r.excluded_reason = "below_filter_config_gate"
