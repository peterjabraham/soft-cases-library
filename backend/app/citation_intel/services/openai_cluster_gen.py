"""
OpenAI-backed novice cluster generation.

Given a plain-language topic, generate a ClusterConfig-shaped JSON payload:
{
  "pillar": "...",
  "clusters": [
    {
      "name": "...",
      "subtopics": [
        { "name": "...", "keywords": ["...", "..."] }
      ]
    }
  ]
}

This service intentionally generates lightweight starter keywords only.
It is not a full keyword expansion stage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

_logger = structlog.get_logger(__name__)

_OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

_SYSTEM_PROMPT = """
You generate citation-intelligence cluster drafts for research discovery.

Return ONLY valid JSON with this exact shape:
{
  "pillar": "string",
  "clusters": [
    {
      "name": "string",
      "subtopics": [
        {
          "name": "string",
          "keywords": ["string", "string", "..."]
        }
      ]
    }
  ]
}

Rules:
- Exactly 1 cluster in `clusters`.
- 4 to 7 subtopics.
- 2 to 4 starter keywords per subtopic.
- Keywords are short search phrases, not sentences.
- Do not include markdown, comments, or extra keys.
- Do not wrap JSON in code fences.
""".strip()


@dataclass
class GeneratedClusterResult:
    cluster_config: dict
    model: str
    usage: dict | None


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _extract_message_content(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:  # pragma: no cover - defensive
        raise ValueError(f"OpenAI response missing message content: {e}")


def _ensure_string(value: object, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _ensure_keywords(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            kw = item.strip()
            if kw:
                out.append(kw)
    # Deduplicate while preserving order
    deduped = list(dict.fromkeys(out))
    # Keep this intentionally small and reviewable
    return deduped[:4]


def _coerce_cluster_shape(raw: dict, topic: str) -> dict:
    pillar = _ensure_string(raw.get("pillar"), "AI Research")
    clusters_raw = raw.get("clusters")
    if not isinstance(clusters_raw, list) or not clusters_raw:
        raise ValueError("Generated JSON missing non-empty 'clusters' array")

    first_cluster = clusters_raw[0] if isinstance(clusters_raw[0], dict) else {}
    cluster_name = _ensure_string(first_cluster.get("name"), topic.strip()[:120] or "Generated Topic")
    subtopics_raw = first_cluster.get("subtopics")
    if not isinstance(subtopics_raw, list) or not subtopics_raw:
        raise ValueError("Generated JSON missing non-empty 'subtopics' array")

    subtopics: list[dict] = []
    for idx, sub in enumerate(subtopics_raw):
        if not isinstance(sub, dict):
            continue
        name = _ensure_string(sub.get("name"), f"Subtopic {idx + 1}")
        keywords = _ensure_keywords(sub.get("keywords"))
        # Enforce strict schema requirement (>=2) by padding deterministic starters.
        if len(keywords) < 2:
            starter = [f"{name.lower()} fundamentals", f"{topic.strip().lower()} {name.lower()}"]
            for s in starter:
                if s not in keywords:
                    keywords.append(s)
                if len(keywords) >= 2:
                    break
        subtopics.append({"name": name, "keywords": keywords[:4]})

    if not subtopics:
        raise ValueError("Generated JSON had no valid subtopics after normalization")

    return {
        "pillar": pillar,
        "clusters": [
            {
                "name": cluster_name,
                "subtopics": subtopics[:7],
            }
        ],
    }


async def generate_cluster_config(
    topic: str,
    api_key: str,
    model: str,
    client: Optional[httpx.AsyncClient] = None,
) -> GeneratedClusterResult:
    """
    Generate a strict ClusterConfig draft from a novice topic.

    Raises:
      ValueError: on invalid/empty model output.
      httpx.HTTPError: on transport/provider failure.
    """
    cleaned_topic = topic.strip()
    if not cleaned_topic:
        raise ValueError("Topic cannot be empty")

    _own_client = client is None
    _client = client or httpx.AsyncClient(timeout=45.0)
    try:
        response = await _client.post(
            _OPENAI_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Topic: "
                            f"{cleaned_topic}\n"
                            "Generate one cluster with practical research subtopics for citation discovery."
                        ),
                    },
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if _own_client:
            await _client.aclose()

    content = _extract_message_content(payload)
    content = _strip_code_fences(content)
    try:
        raw_json = json.loads(content)
    except json.JSONDecodeError as e:
        _logger.error("openai_cluster_invalid_json", error=str(e), content_preview=content[:200])
        raise ValueError("OpenAI returned non-JSON content")

    cluster_config = _coerce_cluster_shape(raw_json, topic=cleaned_topic)
    return GeneratedClusterResult(
        cluster_config=cluster_config,
        model=model,
        usage=payload.get("usage") if isinstance(payload, dict) else None,
    )
