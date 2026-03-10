"""
Perplexity API client — citation URL discovery.

Sends each query_text to the sonar-pro chat completions endpoint.
Extracts the `citations` array from the response (list of URLs).
Returns one RawResultData per URL.

Perplexity's sonar-pro is an online model — citations are returned
automatically. Do NOT send `return_citations` as a parameter; it is
not documented and can trigger HTTP 400 errors on some tiers.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx
import structlog

from app.citation_intel.pipeline.raw_result import RawResultData

_BASE_URL = "https://api.perplexity.ai"
_MODEL = "sonar-pro"
_logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a research librarian specialising in AI and computer security. "
    "When given a search query, find the most authoritative, high-quality sources "
    "on that exact topic. Prioritise: peer-reviewed academic papers, arXiv preprints, "
    "official security advisories, NIST/OWASP publications, and expert practitioner "
    "blogs (e.g. Simon Willison, LangChain blog, Google DeepMind blog). "
    "For each source, include the URL inline. "
    "Return a structured response with one paragraph per major source, "
    "citing title, author/org, and URL. Do not waffle — cite sources directly."
)


async def discover(
    query_text: str,
    subtopic: str,
    pillar: str,
    cluster_name: str,
    api_key: str,
    semaphore: Optional[asyncio.Semaphore] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> list[RawResultData]:
    """
    Call Perplexity sonar-pro and extract citation URLs.

    Returns one RawResultData per URL found in the `citations` array.
    Returns [] on any error (graceful degradation).

    Provide `client` in tests for httpx mocking.
    """
    _sem = semaphore or asyncio.Semaphore(1)
    _own_client = client is None
    _client = client or httpx.AsyncClient(timeout=30.0)

    try:
        async with _sem:
            await asyncio.sleep(1.0)  # respect free-tier rate limit
            response = await _client.post(
                f"{_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": query_text},
                    ],
                    # Do NOT include return_citations — undocumented, causes 400 on some tiers.
                    # sonar-pro is an online model and returns citations automatically.
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = e.response.text[:300]
        except Exception:
            pass
        _logger.error(
            "perplexity_http_error",
            status=e.response.status_code,
            body=body,
            query=query_text[:80],
        )
        return []
    except Exception as e:
        _logger.error("perplexity_request_failed", error=str(e), query=query_text[:80])
        return []
    finally:
        if _own_client:
            await _client.aclose()

    # Citations are a top-level list of URL strings on online models.
    # Some API versions nest them under choices[].message.citations — check both.
    citations: list = data.get("citations", [])

    # Fallback: some model versions return citations inside the message object
    if not citations:
        choice = data.get("choices", [{}])[0]
        citations = choice.get("message", {}).get("citations", [])

    if not citations:
        top_keys = list(data.keys())
        _logger.warning(
            "perplexity_zero_citations",
            query=query_text[:80],
            response_keys=top_keys,
            hint="Check API response format — sonar-pro should return citations for online queries",
        )
        return []

    choice = data.get("choices", [{}])[0]
    snippet = choice.get("message", {}).get("content", "")[:500]

    results: list[RawResultData] = []
    for item in citations:
        # Citations can be plain URL strings or {"url": "...", "title": "..."} objects
        if isinstance(item, str):
            url = item
            title = None
        elif isinstance(item, dict):
            url = item.get("url", "")
            title = item.get("title")
        else:
            continue

        if not url or not url.startswith("http"):
            continue

        results.append(
            RawResultData(
                source_api="perplexity",
                subtopic=subtopic,
                pillar=pillar,
                cluster_name=cluster_name,
                url=url,
                title=title,
                abstract_or_snippet=snippet,
                discovered_by=["perplexity"],
                raw_payload={"query": query_text, "model": _MODEL},
            )
        )

    _logger.info("perplexity_discovered", count=len(results), query=query_text[:80])
    return results
