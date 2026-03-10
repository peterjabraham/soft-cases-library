"""
arXiv API client — preprint discovery.

Uses the arXiv export API (Atom/XML, no key required).
Parses with defusedxml (safe XML parser, no XXE).

Returns up to 20 results per query.
Rate limit: arXiv asks for ≥3s between requests.
We use asyncio.Semaphore(1) + 3s sleep.
"""

from __future__ import annotations

import asyncio
import re
from typing import Optional

import defusedxml.ElementTree as ET
import httpx
import structlog

from app.citation_intel.pipeline.raw_result import RawResultData

_BASE_URL = "https://export.arxiv.org/api/query"
_MAX_RESULTS = 20
_SLEEP = 3.0

# Words to strip from natural-language queries before sending to arXiv Lucene
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "to", "for", "on",
    "with", "using", "via", "is", "are", "be", "as", "at", "by", "from",
}


def _format_arxiv_query(query_text: str) -> str:
    """
    Convert a natural-language query into an arXiv Lucene query.

    arXiv Lucene field syntax quirk: `all:foo bar` only applies the
    `all:` field prefix to "foo" — "bar" becomes free text. The correct
    form is `all:foo AND all:bar` or a quoted phrase `all:"foo bar"`.

    Strategy: strip temporal terms (years) and punctuation, extract
    meaningful tokens, and combine as `all:token AND all:token` so every
    token must appear somewhere in title, abstract, or categories.
    """
    # Remove year numbers (temporal framing not useful for arXiv)
    cleaned = re.sub(r"\b20\d{2}\b", "", query_text)
    # Normalise punctuation that confuses Lucene
    cleaned = re.sub(r"[&\+\|\-\(\)\[\]{}^~*?:\\\"'`]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    tokens = [
        t for t in cleaned.split()
        if t.lower() not in _STOPWORDS and len(t) > 2
    ]

    if not tokens:
        # Fallback: bare keyword search on the first 60 chars
        return f"all:{query_text[:60]}"

    # Keep the most discriminating tokens (max 5) to avoid over-constraining
    core = tokens[:5]
    return " AND ".join(f"all:{t}" for t in core)
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}
_logger = structlog.get_logger(__name__)


def _parse_arxiv_id(id_url: str) -> Optional[str]:
    """Extract arXiv ID from URL like http://arxiv.org/abs/2301.12345v1."""
    if not id_url:
        return None
    parts = id_url.rstrip("/").split("/")
    if parts:
        raw_id = parts[-1]
        # Strip version
        import re
        return re.sub(r"v\d+$", "", raw_id)
    return None


def _parse_entry(entry) -> Optional[RawResultData]:
    """Parse a single Atom <entry> element into RawResultData."""
    try:
        id_el = entry.find("atom:id", _NS)
        id_url = id_el.text.strip() if id_el is not None else None
        arxiv_id = _parse_arxiv_id(id_url)
        url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None

        title_el = entry.find("atom:title", _NS)
        title = " ".join((title_el.text or "").split()) if title_el is not None else None

        summary_el = entry.find("atom:summary", _NS)
        abstract = (summary_el.text or "").strip()[:2000] if summary_el is not None else None

        # Authors
        authors = []
        for author_el in entry.findall("atom:author", _NS):
            name_el = author_el.find("atom:name", _NS)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())
            if len(authors) >= 5:
                break

        # Published date
        pub_el = entry.find("atom:published", _NS)
        published_date = None
        if pub_el is not None and pub_el.text:
            published_date = pub_el.text.strip()[:10]  # YYYY-MM-DD

        # Categories
        categories = []
        for cat_el in entry.findall("atom:category", _NS):
            term = cat_el.get("term", "")
            if term:
                categories.append(term)
        # Primary category
        primary_el = entry.find("arxiv:primary_category", _NS)
        if primary_el is not None:
            primary = primary_el.get("term", "")
            if primary and primary not in categories:
                categories.insert(0, primary)

        # DOI (if available)
        doi_el = entry.find("arxiv:doi", _NS)
        doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None

        return RawResultData(
            source_api="arxiv",
            arxiv_id=arxiv_id,
            url=url,
            doi=doi,
            title=title,
            authors=authors,
            abstract_or_snippet=abstract,
            published_date=published_date,
            arxiv_categories=categories,
            is_preprint=True,
            discovered_by=["arxiv"],
            raw_payload={"arxiv_id": arxiv_id},
        )
    except Exception as e:
        _logger.warning("arxiv_parse_entry_failed", error=str(e))
        return None


def parse_arxiv_response(xml_content: str) -> list[RawResultData]:
    """Parse arXiv Atom XML response. Pure function — used directly in tests."""
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        _logger.error("arxiv_xml_parse_failed", error=str(e))
        return []

    entries = root.findall("atom:entry", _NS)
    results = []
    for entry in entries:
        result = _parse_entry(entry)
        if result:
            results.append(result)
    return results


async def discover(
    query_text: str,
    subtopic: str,
    pillar: str,
    cluster_name: str,
    semaphore: Optional[asyncio.Semaphore] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> list[RawResultData]:
    """
    Query arXiv API and return parsed results.

    Returns [] on error (graceful degradation).
    """
    _sem = semaphore or asyncio.Semaphore(1)
    _own_client = client is None
    _client = client or httpx.AsyncClient(timeout=30.0)

    arxiv_query = _format_arxiv_query(query_text)
    _logger.info("arxiv_query", raw=query_text[:80], formatted=arxiv_query)

    try:
        async with _sem:
            await asyncio.sleep(_SLEEP)
            response = await _client.get(
                _BASE_URL,
                params={
                    "search_query": arxiv_query,
                    "max_results": _MAX_RESULTS,
                    "sortBy": "relevance",
                    "sortOrder": "descending",
                },
            )
            response.raise_for_status()
            xml_content = response.text
    except httpx.HTTPStatusError as e:
        _logger.error("arxiv_http_error", status=e.response.status_code, query=arxiv_query)
        return []
    except Exception as e:
        _logger.error("arxiv_request_failed", error=str(e), query=arxiv_query)
        return []
    finally:
        if _own_client:
            await _client.aclose()

    results = parse_arxiv_response(xml_content)
    for r in results:
        r.subtopic = subtopic
        r.pillar = pillar
        r.cluster_name = cluster_name

    _logger.info("arxiv_discovered", count=len(results), query=arxiv_query)
    return results
