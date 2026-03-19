from __future__ import annotations

import json

import httpx
import pytest
from fastapi import HTTPException

from app.citation_intel.router import ClusterGenerateRequest, generate_cluster
from app.citation_intel.services.openai_cluster_gen import (
    GeneratedClusterResult,
    generate_cluster_config,
)


@pytest.fixture
def required_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/soft_cases")
    monkeypatch.setenv("AUTH_SECRET", "test-secret-which-is-long-enough-for-tests")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.3")


@pytest.mark.asyncio
async def test_generate_cluster_config_success_parses_json():
    payload = {
        "pillar": "AI Security",
        "clusters": [
            {
                "name": "Prompt Injection",
                "subtopics": [
                    {"name": "Attack Vectors", "keywords": ["prompt injection", "jailbreak"]},
                    {"name": "Mitigations", "keywords": ["guardrails", "input sanitization"]},
                ],
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.openai.com/v1/chat/completions")
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "gpt-5.3"
        content = json.dumps(payload)
        return httpx.Response(
            status_code=200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_cluster_config(
            topic="Prompt Injection",
            api_key="sk-test",
            model="gpt-5.3",
            client=client,
        )

    assert result.model == "gpt-5.3"
    assert result.cluster_config["pillar"] == "AI Security"
    assert len(result.cluster_config["clusters"][0]["subtopics"]) == 2
    assert result.usage is not None


@pytest.mark.asyncio
async def test_generate_cluster_config_invalid_json_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="non-JSON"):
            await generate_cluster_config(
                topic="Prompt Injection",
                api_key="sk-test",
                model="gpt-5.3",
                client=client,
            )


@pytest.mark.asyncio
async def test_generate_cluster_endpoint_missing_openai_key(required_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(HTTPException) as exc:
        await generate_cluster(ClusterGenerateRequest(topic="Prompt Injection"))

    assert exc.value.status_code == 503
    assert "OPENAI_API_KEY" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_generate_cluster_endpoint_success(required_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    async def fake_generate_cluster_config(*args, **kwargs):
        return GeneratedClusterResult(
            cluster_config={
                "pillar": "AI Security",
                "clusters": [
                    {
                        "name": "Prompt Injection",
                        "subtopics": [
                            {
                                "name": "Attack Vectors",
                                "keywords": ["prompt injection", "jailbreaking"],
                            }
                        ],
                    }
                ],
            },
            model="gpt-5.3",
            usage={"input_tokens": 1, "output_tokens": 1},
        )

    monkeypatch.setattr(
        "app.citation_intel.services.openai_cluster_gen.generate_cluster_config",
        fake_generate_cluster_config,
    )

    result = await generate_cluster(ClusterGenerateRequest(topic="Prompt Injection"))
    assert result.model == "gpt-5.3"
    assert result.cluster_config["clusters"][0]["name"] == "Prompt Injection"


@pytest.mark.asyncio
async def test_generate_cluster_endpoint_invalid_shape_returns_422(required_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    async def fake_generate_cluster_config(*args, **kwargs):
        return GeneratedClusterResult(
            cluster_config={
                "pillar": "AI Security",
                "clusters": [
                    {
                        "name": "Prompt Injection",
                        "subtopics": [{"name": "Attack Vectors", "keywords": ["only-one"]}],
                    }
                ],
            },
            model="gpt-5.3",
            usage=None,
        )

    monkeypatch.setattr(
        "app.citation_intel.services.openai_cluster_gen.generate_cluster_config",
        fake_generate_cluster_config,
    )

    with pytest.raises(HTTPException) as exc:
        await generate_cluster(ClusterGenerateRequest(topic="Prompt Injection"))

    assert exc.value.status_code == 422
    assert "validation error" in str(exc.value.detail).lower()
