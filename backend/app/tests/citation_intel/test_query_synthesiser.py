"""
Unit tests for query_synthesiser.py — Phase A gate.

All 5 tests must pass before proceeding to Phase B.
"""

import pytest

from app.citation_intel.cluster_parser import SubtopicModel
from app.citation_intel.query_synthesiser import synthesise_all_queries, synthesise_queries


def test_generates_2_to_3_queries_per_subtopic(prompt_injection_subtopic):
    """Subtopic with 5 keywords produces 2 or 3 queries."""
    queries = synthesise_queries(prompt_injection_subtopic)
    assert 2 <= len(queries) <= 3


def test_query_contains_discriminating_keywords(minimal_subtopic):
    """All keywords appear somewhere across the generated queries."""
    queries = synthesise_queries(minimal_subtopic)
    combined = " ".join(queries).lower()

    matched = sum(
        1 for kw in minimal_subtopic.keywords if kw.lower() in combined
    )
    assert matched >= len(minimal_subtopic.keywords), (
        f"Expected all {len(minimal_subtopic.keywords)} keywords in queries, "
        f"found {matched}. Queries: {queries}"
    )


def test_query_does_not_exceed_500_chars(prompt_injection_subtopic):
    """Each generated query is under 500 characters."""
    queries = synthesise_queries(prompt_injection_subtopic)
    for q in queries:
        assert len(q) < 500, f"Query too long ({len(q)} chars): {q!r}"


def test_produces_distinct_queries(prompt_injection_subtopic):
    """No two generated queries are identical."""
    queries = synthesise_queries(prompt_injection_subtopic)
    assert len(queries) == len(set(queries)), f"Duplicate queries found: {queries}"


def test_handles_minimum_keyword_subtopic(minimal_subtopic):
    """Subtopic with 2 keywords (minimum) produces at least 1 query, no exception."""
    queries = synthesise_queries(minimal_subtopic)
    assert len(queries) >= 1
    # Each query must be a non-empty string
    for q in queries:
        assert isinstance(q, str)
        assert len(q.strip()) > 0


def test_synthesise_all_queries_returns_tagged_objects(
    prompt_injection_subtopic,
):
    """synthesise_all_queries returns dicts with all required keys."""
    results = synthesise_all_queries(
        pillar="AI Security",
        cluster_name="Prompt Injection",
        subtopic=prompt_injection_subtopic,
    )
    assert len(results) >= 2
    for item in results:
        assert "pillar" in item
        assert "cluster_name" in item
        assert "subtopic" in item
        assert "query_text" in item
        assert item["pillar"] == "AI Security"
        assert item["cluster_name"] == "Prompt Injection"
        assert item["subtopic"] == "Attack Vectors & Techniques"
