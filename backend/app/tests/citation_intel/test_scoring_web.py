"""
Unit tests for web content (Perplexity) scoring — Phase B gate.
"""

import pytest

from app.citation_intel.pipeline.raw_result import RawResultData
from app.citation_intel.scoring.scorer import (
    RELEVANCE_GATE,
    _W_WEB_RELEVANCE,
    _W_WEB_TIER,
    score_web,
)


def _make_web(url="https://simonwillison.net/2025/anything",
              title="Prompt Injection in Production",
              snippet="prompt injection attacks in production LLM systems require defence",
              source_tier=3):
    return RawResultData(
        source_api="perplexity",
        url=url,
        title=title,
        abstract_or_snippet=snippet,
        source_tier=source_tier,
        tier_multiplier={1: 1.5, 2: 1.2, 3: 1.0, 4: 0.8, 5: 0.6}.get(source_tier, 0.6),
        discovered_by=["perplexity"],
    )


def test_web_formula_weights_sum_to_1():
    assert _W_WEB_RELEVANCE + _W_WEB_TIER == pytest.approx(1.0, abs=1e-6)


def test_web_score_confidence_max_2():
    r = _make_web()
    keywords = ["prompt injection", "defence", "LLM"]
    score_web(r, keywords)
    assert r.score_confidence is not None
    assert r.score_confidence <= 2


def test_t1_web_source_scores_higher_than_t3():
    r_t1 = _make_web(
        url="https://arxiv.org/abs/2302.04237",
        title="Prompt Injection Study",
        snippet="prompt injection attacks adversarial LLM defense systems",
        source_tier=1,
    )
    r_t3 = _make_web(
        url="https://simonwillison.net/post",
        title="Prompt Injection Study",
        snippet="prompt injection attacks adversarial LLM defense systems",
        source_tier=3,
    )
    keywords = ["prompt injection", "adversarial", "LLM", "defense"]
    score_web(r_t1, keywords)
    score_web(r_t3, keywords)

    assert r_t1.final_score > r_t3.final_score


def test_web_below_relevance_gate_excluded():
    r = _make_web(
        title="Stock Market Analysis 2025",
        snippet="equity markets inflation interest rates portfolio allocation",
        source_tier=2,
    )
    keywords = ["prompt injection", "jailbreaking", "adversarial"]
    score_web(r, keywords)
    assert r.topical_relevance == 0.0
    assert r.excluded is True
    assert r.excluded_reason == "below_relevance_gate"


def test_web_final_score_capped_at_100():
    r = _make_web(
        url="https://nist.gov/ai-framework",
        title="Prompt injection",
        snippet="prompt injection",
        source_tier=1,
    )
    keywords = ["prompt injection"]
    score_web(r, keywords)
    assert r.final_score <= 100.0
