"""
Unit tests for cluster_parser.py — Phase A gate.

All 6 tests must pass before proceeding to Phase B.
"""

import pytest
from pydantic import ValidationError

from app.citation_intel.cluster_parser import (
    ClusterModel,
    ParsedCluster,
    SubtopicModel,
    parse_cluster,
)


def test_parses_valid_cluster_json(valid_cluster_dict):
    """A well-formed cluster dict parses without error."""
    result = parse_cluster(valid_cluster_dict)

    assert result.pillar == "AI Security"
    assert len(result.clusters) == 1
    assert result.clusters[0].name == "Prompt Injection"
    assert len(result.clusters[0].subtopics) == 2
    assert result.clusters[0].subtopics[0].name == "Attack Vectors & Techniques"
    assert len(result.clusters[0].subtopics[0].keywords) == 3


def test_rejects_cluster_missing_subtopics():
    """A cluster with no subtopics raises ValidationError."""
    bad = {
        "pillar": "AI Security",
        "clusters": [{"name": "Prompt Injection", "subtopics": []}],
    }
    with pytest.raises(ValidationError):
        parse_cluster(bad)


def test_rejects_subtopic_with_one_keyword():
    """Subtopic with fewer than 2 keywords raises ValidationError."""
    bad = {
        "pillar": "AI Security",
        "clusters": [
            {
                "name": "Prompt Injection",
                "subtopics": [{"name": "Attack Vectors", "keywords": ["prompt injection"]}],
            }
        ],
    }
    with pytest.raises(ValidationError):
        parse_cluster(bad)


def test_rejects_cluster_exceeding_subtopic_limit():
    """A cluster with 11 subtopics raises ValidationError."""
    subtopics = [
        {"name": f"Subtopic {i}", "keywords": ["keyword a", "keyword b"]}
        for i in range(11)
    ]
    bad = {
        "pillar": "AI Security",
        "clusters": [{"name": "Big Cluster", "subtopics": subtopics}],
    }
    with pytest.raises(ValidationError):
        parse_cluster(bad)


def test_accepts_cluster_at_exact_subtopic_limit():
    """A cluster with exactly 10 subtopics is valid."""
    subtopics = [
        {"name": f"Subtopic {i}", "keywords": ["keyword a", "keyword b"]}
        for i in range(10)
    ]
    valid = {
        "pillar": "AI Security",
        "clusters": [{"name": "Big Cluster", "subtopics": subtopics}],
    }
    result = parse_cluster(valid)
    assert len(result.clusters[0].subtopics) == 10


def test_pillar_name_required():
    """An empty pillar name raises ValidationError."""
    bad = {
        "pillar": "",
        "clusters": [
            {
                "name": "Prompt Injection",
                "subtopics": [
                    {"name": "Attack", "keywords": ["prompt injection", "jailbreaking"]}
                ],
            }
        ],
    }
    with pytest.raises(ValidationError):
        parse_cluster(bad)


def test_all_subtopics_helper(valid_cluster_dict):
    """all_subtopics returns correct (pillar, cluster_name, subtopic) tuples."""
    result = parse_cluster(valid_cluster_dict)
    all_subs = result.all_subtopics

    assert len(all_subs) == 2
    pillar, cluster_name, subtopic = all_subs[0]
    assert pillar == "AI Security"
    assert cluster_name == "Prompt Injection"
    assert subtopic.name == "Attack Vectors & Techniques"
