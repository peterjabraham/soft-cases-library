"""
Unit tests for topical relevance calculation — Phase B gate.
"""

import pytest
from app.citation_intel.scoring.scorer import compute_topical_relevance


def test_all_keywords_present_scores_1():
    relevance, matched, density = compute_topical_relevance(
        "prompt injection jailbreaking adversarial prompts",
        ["prompt injection", "jailbreaking", "adversarial prompts"],
    )
    assert relevance == 1.0
    assert len(matched) == 3


def test_no_keywords_present_scores_0():
    relevance, matched, density = compute_topical_relevance(
        "machine learning model training",
        ["prompt injection", "jailbreaking"],
    )
    assert relevance == 0.0
    assert matched == []


def test_partial_keyword_match():
    relevance, matched, density = compute_topical_relevance(
        "this paper discusses prompt injection techniques",
        ["prompt injection", "jailbreaking", "adversarial"],
    )
    assert relevance == pytest.approx(1 / 3, rel=1e-3)
    assert "prompt injection" in matched
    assert "jailbreaking" not in matched


def test_empty_keywords_returns_zero():
    relevance, matched, density = compute_topical_relevance("some text", [])
    assert relevance == 0.0


def test_empty_text_returns_zero():
    relevance, matched, density = compute_topical_relevance("", ["prompt injection"])
    assert relevance == 0.0


def test_density_capped_at_1():
    relevance, matched, density = compute_topical_relevance(
        "prompt injection prompt injection prompt injection",
        ["prompt injection"],
    )
    assert relevance == 1.0


def test_case_insensitive():
    relevance, matched, density = compute_topical_relevance(
        "PROMPT INJECTION attack",
        ["prompt injection"],
    )
    assert relevance == 1.0
