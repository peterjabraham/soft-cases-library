"""
Integration tests for arXiv service client.

Two layers:
  1. parse_arxiv_response() — pure function, no HTTP needed
  2. discover() — with mocked httpx
"""

from pathlib import Path

import httpx
import pytest

from app.citation_intel.services.arxiv import discover, parse_arxiv_response

_FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_response.xml"


@pytest.fixture
def arxiv_xml():
    return _FIXTURE.read_text()


def _mock_client(xml: str, status_code: int = 200) -> httpx.AsyncClient:
    class _Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(
                status_code=status_code,
                content=xml.encode(),
                headers={"content-type": "application/atom+xml"},
                request=request,
            )
    return httpx.AsyncClient(transport=_Transport())


def test_parse_arxiv_response_returns_results(arxiv_xml):
    results = parse_arxiv_response(arxiv_xml)
    assert len(results) == 2
    assert all(r.source_api == "arxiv" for r in results)


def test_parse_arxiv_response_extracts_arxiv_id(arxiv_xml):
    results = parse_arxiv_response(arxiv_xml)
    ids = [r.arxiv_id for r in results]
    assert "2302.04237" in ids
    assert "2307.02483" in ids


def test_parse_arxiv_strips_version_from_id(arxiv_xml):
    results = parse_arxiv_response(arxiv_xml)
    for r in results:
        if r.arxiv_id:
            assert "v" not in r.arxiv_id, f"Version suffix found in: {r.arxiv_id}"


def test_parse_arxiv_extracts_categories(arxiv_xml):
    results = parse_arxiv_response(arxiv_xml)
    first = results[0]
    assert "cs.CR" in first.arxiv_categories or "cs.AI" in first.arxiv_categories


def test_parse_arxiv_extracts_doi(arxiv_xml):
    results = parse_arxiv_response(arxiv_xml)
    first = next(r for r in results if r.arxiv_id == "2302.04237")
    assert first.doi == "10.1145/3576915.3616633"


def test_parse_arxiv_marks_is_preprint(arxiv_xml):
    results = parse_arxiv_response(arxiv_xml)
    assert all(r.is_preprint is True for r in results)


async def test_arxiv_discover_returns_results(arxiv_xml):
    client = _mock_client(arxiv_xml)
    results = await discover(
        query_text="prompt injection",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        client=client,
    )
    assert len(results) == 2
    assert all("arxiv" in r.discovered_by for r in results)


async def test_arxiv_discover_returns_empty_on_error():
    client = _mock_client("", status_code=503)
    results = await discover(
        query_text="prompt injection",
        subtopic="Attack Vectors",
        pillar="AI Security",
        cluster_name="Prompt Injection",
        client=client,
    )
    assert results == []
