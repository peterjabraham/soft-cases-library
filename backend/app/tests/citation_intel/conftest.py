"""
Test configuration for citation intel unit tests.

Phase A tests are pure Python — no database, no HTTP calls.
Fixtures here provide reusable input data.
"""

import pytest
from app.citation_intel.cluster_parser import SubtopicModel


@pytest.fixture
def prompt_injection_subtopic() -> SubtopicModel:
    """A realistic subtopic with 5 keywords."""
    return SubtopicModel(
        name="Attack Vectors & Techniques",
        keywords=[
            "prompt injection",
            "jailbreaking",
            "adversarial prompts",
            "indirect prompt injection",
            "prompt injection attacks",
        ],
    )


@pytest.fixture
def minimal_subtopic() -> SubtopicModel:
    """Subtopic with minimum 2 keywords."""
    return SubtopicModel(
        name="Defence",
        keywords=["prompt injection defense", "input sanitization LLM"],
    )


@pytest.fixture
def valid_cluster_dict() -> dict:
    return {
        "pillar": "AI Security",
        "clusters": [
            {
                "name": "Prompt Injection",
                "subtopics": [
                    {
                        "name": "Attack Vectors & Techniques",
                        "keywords": [
                            "prompt injection",
                            "jailbreaking",
                            "adversarial prompts",
                        ],
                    },
                    {
                        "name": "Defence & Mitigation",
                        "keywords": [
                            "prompt injection defense",
                            "dual LLM pattern",
                            "CaMeL prompt injection",
                        ],
                    },
                ],
            }
        ],
    }
