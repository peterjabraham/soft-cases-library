"""
Unit tests for classifier.py — Phase B gate.
"""

import pytest

from app.citation_intel.pipeline.classifier import classify, TIER_MULTIPLIERS
from app.citation_intel.pipeline.raw_result import RawResultData


def _make(source_api="perplexity", url=None, arxiv_categories=None, venue=None, arxiv_id=None):
    return RawResultData(
        source_api=source_api,
        url=url,
        arxiv_categories=arxiv_categories or [],
        venue=venue,
        arxiv_id=arxiv_id,
        discovered_by=[source_api],
    )


def test_edu_domain_is_tier_1():
    r = _make(url="https://ai.stanford.edu/paper")
    classify(r)
    assert r.source_tier == 1
    assert r.tier_multiplier == 1.5


def test_gov_domain_is_tier_1():
    r = _make(url="https://nist.gov/ai-framework")
    classify(r)
    assert r.source_tier == 1


def test_arxiv_org_is_tier_1():
    r = _make(source_api="arxiv", url="https://arxiv.org/abs/2302.04237")
    classify(r)
    assert r.source_tier == 1


def test_arxiv_cs_ai_category_is_tier_1():
    r = _make(source_api="arxiv", arxiv_categories=["cs.AI"])
    classify(r)
    assert r.category_tier == 1


def test_arxiv_cs_cr_category_is_tier_1():
    r = _make(source_api="arxiv", arxiv_categories=["cs.CR", "cs.LG"])
    classify(r)
    assert r.category_tier == 1


def test_arxiv_unknown_category_is_tier_2():
    r = _make(source_api="arxiv", arxiv_categories=["econ.GN"])
    classify(r)
    assert r.category_tier == 2


def test_simonwillison_is_tier_3():
    r = _make(url="https://simonwillison.net/2025/anything")
    classify(r)
    assert r.source_tier == 3


def test_unknown_domain_is_tier_4_or_5():
    r = _make(url="https://randomnewblog.io/post")
    classify(r)
    assert r.source_tier in (4, 5)


def test_semantic_scholar_result_classified_as_academic():
    r = _make(source_api="semantic_scholar", url="https://doi.org/10.1234/paper")
    classify(r)
    assert r.content_type == "academic"


def test_perplexity_hbr_is_news_or_blog():
    r = _make(source_api="perplexity", url="https://hbr.org/2025/prompt-ai")
    classify(r)
    assert r.content_type in ("news", "blog")


def test_perplexity_simonwillison_is_blog():
    r = _make(source_api="perplexity", url="https://simonwillison.net/series/prompt-injection/")
    classify(r)
    assert r.content_type == "blog"


def test_arxiv_result_marked_is_preprint():
    r = _make(source_api="arxiv", url="https://arxiv.org/abs/2302.04237", arxiv_id="2302.04237")
    classify(r)
    assert r.is_preprint is True


def test_tier_multipliers_cover_all_tiers():
    for tier in range(1, 6):
        assert tier in TIER_MULTIPLIERS
    assert TIER_MULTIPLIERS[1] > TIER_MULTIPLIERS[2] > TIER_MULTIPLIERS[3]
