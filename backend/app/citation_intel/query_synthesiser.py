"""
Query synthesiser — generates 2–3 search queries per subtopic.

Strategy: combine discriminating keywords into distinct natural-language queries
using different keyword subsets. No LLM call — deterministic.

Rules:
  - Each query must be < 500 characters
  - Each query must contain at least 1 keyword from the subtopic
  - All generated queries must be distinct
  - Minimum 2 queries per subtopic (given min 2 keywords)
  - Maximum 3 queries per subtopic
"""

from __future__ import annotations

from app.citation_intel.cluster_parser import SubtopicModel


def synthesise_queries(subtopic: SubtopicModel) -> list[str]:
    """
    Generate 2-3 distinct search queries for a subtopic.

    Uses three templates over different keyword slices:
      Q1: first 3 keywords joined — core terms
      Q2: keywords offset by 1, plus subtopic name for context
      Q3: last 3 keywords with temporal framing (2025 2026)

    Returns 2–3 distinct queries, each < 500 characters.
    """
    keywords = subtopic.keywords
    n = len(keywords)
    queries: list[str] = []

    # Q1: first 1-3 keywords — the most discriminating
    slice1 = keywords[: min(3, n)]
    q1 = " ".join(slice1)
    queries.append(q1)

    # Q2: offset slice with subtopic name for broader intent
    if n >= 3:
        start = 1
        slice2 = keywords[start : start + 3]
        q2 = subtopic.name + " " + " ".join(slice2)
    elif n == 2:
        # Only 2 keywords — use both with the subtopic name
        q2 = subtopic.name + " " + " ".join(keywords)
    else:
        q2 = None  # type: ignore[assignment]

    if q2 and q2 != q1 and q2 not in queries:
        queries.append(q2)

    # Q3: last keywords with temporal framing — surfaces recent content
    if n >= 4:
        slice3 = keywords[max(0, n - 3) :]
        q3 = " ".join(slice3) + " 2025 2026"
        if q3 not in queries:
            queries.append(q3)

    # Enforce 500-char limit and return up to 3
    truncated = [q[:499] for q in queries]
    return truncated[:3]


def synthesise_all_queries(
    pillar: str,
    cluster_name: str,
    subtopic: SubtopicModel,
) -> list[dict]:
    """
    Generate tagged query objects for a subtopic.

    Returns list of dicts:
    { "pillar": str, "cluster_name": str, "subtopic": str, "query_text": str }
    """
    queries = synthesise_queries(subtopic)
    return [
        {
            "pillar": pillar,
            "cluster_name": cluster_name,
            "subtopic": subtopic.name,
            "query_text": q,
        }
        for q in queries
    ]
