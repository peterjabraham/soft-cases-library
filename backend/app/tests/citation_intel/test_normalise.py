"""
Unit tests for batch normaliser — Phase B gate.
"""

import pytest

from app.citation_intel.pipeline.raw_result import RawResultData
from app.citation_intel.scoring.normaliser import (
    normalise_citation_signals,
    _citation_velocity,
    _age_months,
)


def _make_ss(citation_count, recent=None, influential=0, published_date="2023-01-01"):
    r = RawResultData(
        source_api="semantic_scholar",
        citation_count=citation_count,
        recent_citations=recent,
        influential_citations=influential,
        published_date=published_date,
        discovered_by=["semantic_scholar"],
    )
    return r


def test_citation_velocity_calculation():
    """120 citations in 24 months → velocity 5.0."""
    r = _make_ss(citation_count=120, published_date="2023-01-01")
    r.recent_citations = 120
    # Age depends on today; use citation_count ÷ age as approximation
    # Test the core math directly via _citation_velocity
    # Patch published_date to force a known age
    r.published_date = "2022-01-01"  # ~26 months ago from 2024-03-04
    vel = _citation_velocity(r)
    # Velocity = 120 / age_months(2022-01-01)
    age = _age_months("2022-01-01")
    expected = round(120 / age, 4)
    assert vel == pytest.approx(expected, rel=1e-3)


def test_citation_velocity_zero_age_does_not_divide_by_zero():
    """Paper published today — velocity should be 0, not ZeroDivisionError."""
    from datetime import date
    today = date.today().isoformat()
    r = _make_ss(citation_count=10, published_date=today)
    vel = _citation_velocity(r)
    assert vel == 0.0


def test_age_months_parses_year_only():
    months = _age_months("2023")
    assert months > 0


def test_age_months_parses_year_month():
    months = _age_months("2023-06")
    assert months > 0


def test_age_months_returns_zero_for_garbage():
    assert _age_months("not-a-date") == 0
    assert _age_months(None) == 0


def test_normalise_batch_produces_0_to_1_range():
    r1 = _make_ss(citation_count=0, recent=0, influential=0, published_date="2020-01-01")
    r2 = _make_ss(citation_count=100, recent=100, influential=20, published_date="2020-01-01")
    r3 = _make_ss(citation_count=50, recent=50, influential=10, published_date="2020-01-01")

    normalise_citation_signals([r1, r2, r3])

    for r in [r1, r2, r3]:
        v_norm = getattr(r, "_velocity_norm", None)
        i_norm = getattr(r, "_influential_norm", None)
        assert v_norm is not None
        assert i_norm is not None
        assert 0.0 <= v_norm <= 1.0
        assert 0.0 <= i_norm <= 1.0


def test_normalise_all_same_velocity_returns_0_5():
    """All same velocity → min-max returns 0.5 (not divide-by-zero)."""
    r1 = _make_ss(citation_count=50, recent=50, published_date="2022-01-01")
    r2 = _make_ss(citation_count=50, recent=50, published_date="2022-01-01")
    normalise_citation_signals([r1, r2])
    assert getattr(r1, "_velocity_norm") == pytest.approx(0.5)
    assert getattr(r2, "_velocity_norm") == pytest.approx(0.5)


def test_non_ss_results_get_zero_norms():
    r_web = RawResultData(source_api="perplexity", discovered_by=["perplexity"])
    r_arxiv = RawResultData(source_api="arxiv", discovered_by=["arxiv"])
    normalise_citation_signals([r_web, r_arxiv])
    assert getattr(r_web, "_velocity_norm", None) == 0.0
    assert getattr(r_arxiv, "_velocity_norm", None) == 0.0
