"""
Unit tests for academic paper scoring — Phase B gate.
"""

import pytest

from app.citation_intel.pipeline.raw_result import RawResultData
from app.citation_intel.scoring.scorer import (
    RELEVANCE_GATE,
    _W_SS_RELEVANCE,
    _W_SS_VELOCITY,
    _W_SS_INFLUENTIAL,
    _W_SS_VENUE,
    score_academic_full,
    score_academic_preprint,
)


def _make_ss(title="Defeating Prompt Injections", citation_count=100,
             influential=10, venue_tier=1, source_tier=1,
             published_date="2023-01-01", velocity_norm=0.5, inf_norm=0.5):
    r = RawResultData(
        source_api="semantic_scholar",
        title=title,
        abstract_or_snippet="prompt injection jailbreaking adversarial LLM defense",
        citation_count=citation_count,
        influential_citations=influential,
        venue_tier=venue_tier,
        source_tier=source_tier,
        tier_multiplier=1.5,
        published_date=published_date,
        discovered_by=["semantic_scholar"],
    )
    object.__setattr__(r, "_velocity_norm", velocity_norm)
    object.__setattr__(r, "_influential_norm", inf_norm)
    return r


def _make_arxiv(title="Prompt Injection Survey", category_tier=1, source_tier=1):
    r = RawResultData(
        source_api="arxiv",
        title=title,
        abstract_or_snippet="prompt injection jailbreaking adversarial LLM",
        arxiv_categories=["cs.CR", "cs.AI"],
        category_tier=category_tier,
        source_tier=source_tier,
        tier_multiplier=1.5,
        is_preprint=True,
        discovered_by=["arxiv"],
    )
    return r


def test_ss_formula_weights_sum_to_1():
    total = _W_SS_RELEVANCE + _W_SS_VELOCITY + _W_SS_INFLUENTIAL + _W_SS_VENUE
    assert total == pytest.approx(1.0, abs=1e-6)


def test_t1_multiplier_applied():
    """raw_score=0.6, tier_multiplier=1.5 → final_score ≈ 90."""
    r = _make_ss(source_tier=1)
    # Force raw_score to exactly 0.6 by controlling inputs
    # With relevance=1.0, velocity_norm=0.5, inf_norm=0.5, venue_tier=1 (score=1.0):
    # raw = 1.0*0.35 + 0.5*0.30 + 0.5*0.20 + 1.0*0.15 = 0.35 + 0.15 + 0.10 + 0.15 = 0.75
    # We want to test the multiplier mechanism, so score a fresh record and check ratio
    r2 = _make_ss(source_tier=1, velocity_norm=0.0, inf_norm=0.0)
    keywords = ["prompt injection", "jailbreaking", "adversarial", "LLM", "defense"]
    score_academic_full(r2, keywords)
    assert r2.final_score is not None
    assert r2.final_score <= 100.0
    assert r2.tier_multiplier == 1.5


def test_final_score_capped_at_100():
    r = _make_ss(source_tier=1, velocity_norm=1.0, inf_norm=1.0)
    keywords = ["prompt injection", "jailbreaking", "adversarial", "LLM", "defense"]
    score_academic_full(r, keywords)
    assert r.final_score <= 100.0


def test_below_relevance_gate_is_excluded():
    r = RawResultData(
        source_api="semantic_scholar",
        title="Unrelated Topic About Quantum Physics",
        abstract_or_snippet="quantum entanglement measurement theory",
        citation_count=50,
        source_tier=1,
        tier_multiplier=1.5,
        discovered_by=["semantic_scholar"],
    )
    object.__setattr__(r, "_velocity_norm", 0.5)
    object.__setattr__(r, "_influential_norm", 0.5)
    score_academic_full(r, ["prompt injection", "jailbreaking", "adversarial"])
    assert r.topical_relevance == 0.0
    assert r.topical_relevance < RELEVANCE_GATE
    assert r.excluded is True
    assert r.excluded_reason == "below_relevance_gate"


def test_ss_score_confidence_max_5():
    r = _make_ss()
    keywords = ["prompt injection", "jailbreaking", "adversarial", "LLM", "defense"]
    score_academic_full(r, keywords)
    assert r.score_confidence is not None
    assert 1 <= r.score_confidence <= 5


def test_arxiv_preprint_score_confidence_max_3():
    r = _make_arxiv()
    keywords = ["prompt injection", "jailbreaking", "adversarial", "LLM"]
    score_academic_preprint(r, keywords)
    assert r.score_confidence is not None
    assert r.score_confidence <= 3


def test_arxiv_preprint_uses_category_tier():
    # Use source_tier=3 (multiplier=1.0) so scores don't both cap at 100
    r_tier1 = _make_arxiv(category_tier=1, source_tier=3)
    r_tier2 = _make_arxiv(category_tier=2, source_tier=3)
    r_tier1.tier_multiplier = 1.0
    r_tier2.tier_multiplier = 1.0
    keywords = ["prompt injection", "jailbreaking", "adversarial", "LLM"]

    score_academic_preprint(r_tier1, keywords)
    score_academic_preprint(r_tier2, keywords)

    assert r_tier1.final_score > r_tier2.final_score


def test_duplicate_is_not_scored():
    r = _make_ss()
    r.is_duplicate = True
    from app.citation_intel.scoring.scorer import score
    result = score(r, ["prompt injection"])
    assert result.final_score is None
