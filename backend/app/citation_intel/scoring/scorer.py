"""
Scorer — computes authority scores for each result.

Three scoring formulas:
  1. academic_full: SS paper with full citation data
  2. academic_preprint: arXiv paper with no citation data
  3. web: Perplexity-discovered URL

Topical relevance is computed here (keyword density).
Relevance gate: topical_relevance < 0.25 → excluded.

Scoring is deterministic given the input values. No external calls.
"""

from __future__ import annotations

from typing import Optional

from app.citation_intel.pipeline.raw_result import RawResultData
from app.citation_intel.pipeline.classifier import TIER_MULTIPLIERS

# Formula weights
_W_SS_RELEVANCE = 0.35
_W_SS_VELOCITY = 0.30
_W_SS_INFLUENTIAL = 0.20
_W_SS_VENUE = 0.15

_W_ARXIV_RELEVANCE = 0.60
_W_ARXIV_CATEGORY = 0.40

_W_WEB_RELEVANCE = 0.70
_W_WEB_TIER = 0.30

# Relevance gate (hard rule)
RELEVANCE_GATE = 0.25

# Max confidence per type
_CONF_SS = 5
_CONF_ARXIV = 3
_CONF_WEB = 2


def compute_topical_relevance(text: str, keywords: list[str]) -> tuple[float, list[str], float]:
    """
    Compute topical relevance from keyword presence in text.

    Returns (relevance_score, matched_keywords, density).
    - relevance_score = fraction of keywords present in text, capped at 1.0
    - matched_keywords = list of keywords that appeared
    - density = same as relevance_score (for clarity in DB)
    """
    if not keywords or not text:
        return 0.0, [], 0.0
    text_lower = text.lower()
    matched = [kw for kw in keywords if kw.lower() in text_lower]
    density = len(matched) / len(keywords)
    return min(density, 1.0), matched, density


def _venue_tier_score(venue_tier: Optional[int]) -> float:
    """Convert venue_tier (1-2) to 0-1 score."""
    if venue_tier == 1:
        return 1.0
    if venue_tier == 2:
        return 0.5
    return 0.0


def _category_tier_score(category_tier: Optional[int]) -> float:
    """Convert arXiv category_tier (1-2) to 0-1 score."""
    if category_tier == 1:
        return 1.0
    return 0.5  # tier 2 or unknown


def _source_tier_score(source_tier: Optional[int]) -> float:
    """Convert source_tier (1-5) to 0-1 score."""
    mapping = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25, 5: 0.0}
    return mapping.get(source_tier or 5, 0.0)


def _apply_multiplier(raw_score: float, source_tier: Optional[int]) -> tuple[float, float]:
    """Apply tier multiplier, cap at 100. Returns (final_score, multiplier)."""
    multiplier = TIER_MULTIPLIERS.get(source_tier or 5, 0.6)
    final = min(raw_score * multiplier * 100, 100.0)
    return round(final, 2), multiplier


def score_academic_full(result: RawResultData, keywords: list[str]) -> RawResultData:
    """
    Score a Semantic Scholar result with full citation data.

    Uses: topical_relevance, citation_velocity_norm, influential_norm, venue_tier.
    """
    text = f"{result.title or ''} {result.abstract_or_snippet or ''}"
    relevance, matched, density = compute_topical_relevance(text, keywords)
    result.topical_relevance = relevance
    result.matched_keywords = matched
    result.keyword_density = density

    if relevance < RELEVANCE_GATE:
        result.excluded = True
        result.excluded_reason = "below_relevance_gate"
        result.score_confidence = 0
        result.final_score = 0.0
        result.raw_score = 0.0
        return result

    vel_norm = getattr(result, "_velocity_norm", 0.0)
    inf_norm = getattr(result, "_influential_norm", 0.0)
    venue_score = _venue_tier_score(result.venue_tier)

    raw = (
        relevance * _W_SS_RELEVANCE
        + vel_norm * _W_SS_VELOCITY
        + inf_norm * _W_SS_INFLUENTIAL
        + venue_score * _W_SS_VENUE
    )
    result.raw_score = round(raw, 4)

    final, multiplier = _apply_multiplier(raw, result.source_tier)
    result.final_score = final
    result.tier_multiplier = multiplier

    # Confidence: count available signals
    signals = [
        relevance > 0,
        (result.citation_velocity or 0) > 0,
        (result.influential_citations or 0) > 0,
        result.venue_tier is not None,
        result.source_tier is not None,
    ]
    result.score_confidence = min(sum(signals), _CONF_SS)
    return result


def score_academic_preprint(result: RawResultData, keywords: list[str]) -> RawResultData:
    """
    Score an arXiv preprint. No citation data available.

    Uses: topical_relevance, category_tier.
    """
    text = f"{result.title or ''} {result.abstract_or_snippet or ''}"
    relevance, matched, density = compute_topical_relevance(text, keywords)
    result.topical_relevance = relevance
    result.matched_keywords = matched
    result.keyword_density = density

    if relevance < RELEVANCE_GATE:
        result.excluded = True
        result.excluded_reason = "below_relevance_gate"
        result.score_confidence = 0
        result.final_score = 0.0
        result.raw_score = 0.0
        return result

    cat_score = _category_tier_score(result.category_tier)
    raw = relevance * _W_ARXIV_RELEVANCE + cat_score * _W_ARXIV_CATEGORY
    result.raw_score = round(raw, 4)

    final, multiplier = _apply_multiplier(raw, result.source_tier)
    result.final_score = final
    result.tier_multiplier = multiplier

    signals = [
        relevance > 0,
        result.category_tier is not None,
    ]
    result.score_confidence = min(sum(signals), _CONF_ARXIV)
    return result


def score_web(result: RawResultData, keywords: list[str]) -> RawResultData:
    """
    Score a Perplexity-discovered URL. No citation data.

    Uses: topical_relevance, source_tier.
    """
    text = f"{result.title or ''} {result.abstract_or_snippet or ''}"
    relevance, matched, density = compute_topical_relevance(text, keywords)
    result.topical_relevance = relevance
    result.matched_keywords = matched
    result.keyword_density = density

    if relevance < RELEVANCE_GATE:
        result.excluded = True
        result.excluded_reason = "below_relevance_gate"
        result.score_confidence = 0
        result.final_score = 0.0
        result.raw_score = 0.0
        return result

    tier_score = _source_tier_score(result.source_tier)
    raw = relevance * _W_WEB_RELEVANCE + tier_score * _W_WEB_TIER
    result.raw_score = round(raw, 4)

    final, multiplier = _apply_multiplier(raw, result.source_tier)
    result.final_score = final
    result.tier_multiplier = multiplier

    signals = [relevance > 0, result.source_tier is not None]
    result.score_confidence = min(sum(signals), _CONF_WEB)
    return result


def score(result: RawResultData, keywords: list[str]) -> RawResultData:
    """
    Route to the correct scoring formula based on content_type and source.
    """
    if result.is_duplicate:
        return result  # Never score duplicates

    if result.source_api == "semantic_scholar" and result.citation_count is not None:
        return score_academic_full(result, keywords)
    elif result.source_api in ("arxiv",) or result.is_preprint:
        return score_academic_preprint(result, keywords)
    else:
        return score_web(result, keywords)


def score_batch(results: list[RawResultData], keywords: list[str]) -> list[RawResultData]:
    """Score all non-duplicate results in a batch."""
    for r in results:
        if not r.is_duplicate:
            score(r, keywords)
    return results
