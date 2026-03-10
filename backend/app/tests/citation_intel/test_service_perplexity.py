"""
Integration tests for Perplexity service client.

All HTTP is mocked via httpx.MockTransport — no real API calls.
"""

import json
from pathlib import Path

import httpx
import pytest

from app.citation_intel.services.perplexity import discover

_FIXTURE = Path(__file__).parent / "fixtures" / "perplexity_response.json"


@pytest.fixture
def perplexity_mock_response():
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


async def test_perplexity_returns_raw_results(perplexity_mock_response):
    client = _mock_client(perplexity_mock_response)
    results = await discover(
        query_text="prompt injection attacks LLM",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        api_key="test-key",
        client=client,
    )
    assert len(results) == 3
    assert all(r.source_api == "perplexity" for r in results)
    assert all(r.url.startswith("http") for r in results)


async def test_perplexity_maps_subtopic_and_pillar(perplexity_mock_response):
    client = _mock_client(perplexity_mock_response)
    results = await discover(
        query_text="prompt injection",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        api_key="test-key",
        client=client,
    )
    for r in results:
        assert r.subtopic == "Attack Vectors"
        assert r.pillar == "AI Security"
        assert r.cluster_name == "Prompt Injection"
        assert "perplexity" in r.discovered_by


async def test_perplexity_returns_empty_on_no_citations(perplexity_mock_response):
    no_citations = {**perplexity_mock_response, "citations": []}
    client = _mock_client(no_citations)
    results = await discover(
        query_text="prompt injection",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        api_key="test-key",
        client=client,
    )
    assert results == []


async def test_perplexity_returns_empty_on_http_error():
    client = _mock_client({}, status_code=429)
    results = await discover(
        query_text="prompt injection",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        api_key="test-key",
        client=client,
    )
    assert results == []
