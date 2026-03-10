"""
Semantic Scholar API client — academic paper discovery.

Uses the free Graph API (no key required) with optional partner key
for higher rate limits (10 req/sec vs 1 req/sec).

Free tier: asyncio.Semaphore(1) + 1s sleep between requests.
Partner tier: asyncio.Semaphore(10) + 0.1s sleep.

Returns one RawResultData per paper found, including citation signals.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx
import structlog

from app.citation_intel.pipeline.raw_result import RawResultData

_BASE_URL = "https://api.semanticscholar.org/graph/v1"
_FIELDS = ",".join([
    "title", "authors", "year", "externalIds",
    "citationCount", "influentialCitationCount",
    "venue", "publicationVenue", "publicationTypes",
    "abstract",
])
_MAX_RESULTS = 20
_logger = structlog.get_logger(__name__)


def _parse_paper(paper: dict, subtopic: str, pillar: str, cluster_name: str) -> RawResultData:
    """Parse a Semantic Scholar paper dict into RawResultData."""
    external_ids = paper.get("externalIds") or {}
    doi = external_ids.get("DOI")
    arxiv_id = external_ids.get("ArXiv")

    authors = [a.get("name", "") for a in (paper.get("authors") or [])[:5]]

    year = paper.get("year")
    published_date = str(year) if year else None

    venue = None
    pub_venue = paper.get("publicationVenue")
    if pub_venue:
        venue = pub_venue.get("name") or pub_venue.get("alternate_names", [None])[0]
    if not venue:
        venue = paper.get("venue")

    # arXiv URL if no DOI
    url = None
    if doi:
        url = f"https://doi.org/{doi}"
    elif arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"

    return RawResultData(
        source_api="semantic_scholar",
        subtopic=subtopic,
        pillar=pillar,
        cluster_name=cluster_name,
        url=url,
        doi=doi,
        arxiv_id=arxiv_id,
        title=paper.get("title"),
        authors=authors,
        abstract_or_snippet=(paper.get("abstract") or "")[:2000],
        published_date=published_date,
        venue=venue,
        citation_count=paper.get("citationCount"),
        influential_citations=paper.get("influentialCitationCount"),
        discovered_by=["semantic_scholar"],
        raw_payload={"paperId": paper.get("paperId")},
    )


async def discover(
    query_text: str,
    subtopic: str,
    pillar: str,
    cluster_name: str,
    api_key: Optional[str] = None,
    semaphore: Optional[asyncio.Semaphore] = None,
    sleep_between: float = 1.0,
    client: Optional[httpx.AsyncClient] = None,
) -> list[RawResultData]:
    """
    Query Semantic Scholar paper search and return results.

    Returns [] on rate limit or error (graceful degradation with warning).
    """
    _sem = semaphore or asyncio.Semaphore(1)
    _own_client = client is None
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key
    _client = client or httpx.AsyncClient(timeout=20.0, headers=headers)

    try:
        async with _sem:
            await asyncio.sleep(sleep_between)
            response = await _client.get(
                f"{_BASE_URL}/paper/search",
                params={
                    "query": query_text,
                    "fields": _FIELDS,
                    "limit": _MAX_RESULTS,
                },
            )
            if response.status_code == 429:
                _logger.warning(
                    "semantic_scholar_rate_limited",
                    query=query_text[:80],
                    hint="Add SEMANTIC_SCHOLAR_API_KEY for 10x higher rate limit",
                )
                return []
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        _logger.error("semantic_scholar_http_error", status=e.response.status_code, query=query_text[:80])
        return []
    except Exception as e:
        _logger.error("semantic_scholar_request_failed", error=str(e), query=query_text[:80])
        return []
    finally:
        if _own_client:
            await _client.aclose()

    papers = data.get("data", [])
    if not papers:
        return []

    return [
        _parse_paper(p, subtopic, pillar, cluster_name)
        for p in papers
        if isinstance(p, dict)
    ]
