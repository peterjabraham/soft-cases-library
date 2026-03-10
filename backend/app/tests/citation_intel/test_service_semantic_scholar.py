"""
Integration tests for Semantic Scholar service client.

All HTTP is mocked — no real API calls.
"""

import json
from pathlib import Path

import httpx
import pytest

from app.citation_intel.services.semantic_scholar import discover

_FIXTURE = Path(__file__).parent / "fixtures" / "semantic_scholar_response.json"


@pytest.fixture
def ss_mock_response():
    return json.loads(_FIXTURE.read_text())


def _mock_client(response_json: dict, status_code: int = 200) -> httpx.AsyncClient:
    class _Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(
                status_code=status_code,
                json=response_json,
                request=request,
            )
    return httpx.AsyncClient(transport=_Transport())


async def test_ss_returns_raw_results(ss_mock_response):
    client = _mock_client(ss_mock_response)
    results = await discover(
        query_text="prompt injection attacks",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        sleep_between=0.0,
        client=client,
    )
    assert len(results) == 2
    assert all(r.source_api == "semantic_scholar" for r in results)


async def test_ss_maps_citation_data(ss_mock_response):
    client = _mock_client(ss_mock_response)
    results = await discover(
        query_text="prompt injection",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        sleep_between=0.0,
        client=client,
    )
    first = results[0]
    assert first.citation_count == 120
    assert first.influential_citations == 18
    assert first.doi == "10.1234/prompt-injection-2024"
    assert first.arxiv_id == "2401.12345"


async def test_ss_maps_venue(ss_mock_response):
    client = _mock_client(ss_mock_response)
    results = await discover(
        query_text="prompt injection",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        sleep_between=0.0,
        client=client,
    )
    assert results[0].venue == "NeurIPS 2024"


async def test_ss_returns_empty_on_rate_limit():
    client = _mock_client({}, status_code=429)
    results = await discover(
        query_text="prompt injection",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        sleep_between=0.0,
        client=client,
    )
    assert results == []


async def test_ss_maps_discovered_by(ss_mock_response):
    client = _mock_client(ss_mock_response)
    results = await discover(
        query_text="prompt injection",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        sleep_between=0.0,
        client=client,
    )
    assert all("semantic_scholar" in r.discovered_by for r in results)
