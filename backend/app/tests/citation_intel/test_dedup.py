"""
Unit tests for deduplicator.py — Phase B gate.
"""

import pytest

from app.citation_intel.pipeline.deduplicator import (
    deduplicate,
    normalise_url,
    normalise_doi,
    normalise_arxiv_id,
)
from app.citation_intel.pipeline.raw_result import RawResultData


def _make(source_api="perplexity", url=None, doi=None, arxiv_id=None, title=None):
    return RawResultData(
        source_api=source_api,
        url=url,
        doi=doi,
        arxiv_id=arxiv_id,
        title=title,
        discovered_by=[source_api],
    )


# ── URL normalisation ─────────────────────────────────────────────────────────

def test_url_normalise_strips_trailing_slash():
    key1 = normalise_url("https://example.com/path/")
    key2 = normalise_url("https://example.com/path")
    assert key1 == key2


def test_url_normalise_forces_https():
    key1 = normalise_url("http://example.com/path")
    key2 = normalise_url("https://example.com/path")
    assert key1 == key2


def test_url_normalise_strips_utm_params():
    key1 = normalise_url("https://example.com/article?utm_source=twitter&utm_medium=social")
    key2 = normalise_url("https://example.com/article")
    assert key1 == key2


def test_url_normalise_preserves_meaningful_params():
    key1 = normalise_url("https://arxiv.org/abs/2302.04237?context=cs")
    key2 = normalise_url("https://arxiv.org/abs/2302.04237")
    # context=cs is NOT a tracking param, so the keyed URL differs from the clean one
    assert key1 != key2


# ── DOI normalisation ─────────────────────────────────────────────────────────

def test_normalise_doi_strips_doi_org_prefix():
    assert normalise_doi("https://doi.org/10.1234/paper") == "10.1234/paper"


def test_normalise_doi_lowercases():
    assert normalise_doi("10.1234/PAPER") == "10.1234/paper"


# ── arXiv ID normalisation ────────────────────────────────────────────────────

def test_normalise_arxiv_id_strips_version():
    assert normalise_arxiv_id("2302.04237v2") == "2302.04237"
    assert normalise_arxiv_id("2302.04237") == "2302.04237"


# ── Dedup logic ────────────────────────────────────────────────────────────────

def test_identical_urls_after_utm_strip_are_duplicates():
    r1 = _make(url="https://example.com/article")
    r2 = _make(url="https://example.com/article?utm_source=twitter")
    results = deduplicate([r1, r2])
    assert r1.is_duplicate is False
    assert r2.is_duplicate is True


def test_doi_match_across_sources_merges_records():
    r1 = _make(source_api="semantic_scholar", doi="10.1234/paper")
    r2 = _make(source_api="arxiv", doi="10.1234/paper")
    r2.discovered_by = ["arxiv"]
    results = deduplicate([r1, r2])
    assert r1.is_duplicate is False
    assert r2.is_duplicate is True
    assert "arxiv" in r1.discovered_by


def test_arxiv_id_match_merges_records():
    r1 = _make(source_api="semantic_scholar", arxiv_id="2301.12345")
    r1.citation_count = 100
    r2 = _make(source_api="arxiv", arxiv_id="2301.12345")
    results = deduplicate([r1, r2])
    assert r2.is_duplicate is True
    # Canonical keeps citation data
    assert r1.citation_count == 100


def test_different_urls_same_domain_are_not_duplicates():
    r1 = _make(url="https://arxiv.org/abs/2301.11111")
    r2 = _make(url="https://arxiv.org/abs/2301.22222")
    results = deduplicate([r1, r2])
    assert r1.is_duplicate is False
    assert r2.is_duplicate is False


def test_null_url_null_doi_null_arxiv_not_merged():
    """Two results with all null identifiers and distinct titles — don't merge."""
    r1 = _make(url=None, doi=None, arxiv_id=None, title="Quantum Computing Hardware Survey")
    r2 = _make(url=None, doi=None, arxiv_id=None, title="Deep Learning in Medical Imaging")
    results = deduplicate([r1, r2])
    assert r1.is_duplicate is False
    assert r2.is_duplicate is False


def test_title_similarity_fallback_merges_near_identical_titles():
    r1 = _make(title="Defeating Prompt Injections by Design")
    r2 = _make(title="Defeating Prompt Injections by Design ")  # trailing space
    results = deduplicate([r1, r2])
    assert r2.is_duplicate is True
