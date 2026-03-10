"""
Cluster parser — validates and parses hierarchical cluster JSON into typed models.

Input format:
{
  "pillar": "AI Security",
  "clusters": [
    {
      "name": "Prompt Injection",
      "subtopics": [
        {
          "name": "Attack Vectors & Techniques",
          "keywords": ["prompt injection", "jailbreaking", ...]
        }
      ]
    }
  ]
}

Validation rules:
  - pillar: non-empty string
  - clusters: 1+ clusters
  - subtopics per cluster: 1–10
  - keywords per subtopic: 2–20
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class SubtopicModel(BaseModel):
    """A single subtopic with its discriminating keywords."""

    name: str = Field(..., min_length=1, description="Subtopic name")
    keywords: list[str] = Field(
        ...,
        min_length=2,
        description="2–20 discriminating keywords for this subtopic",
    )

    @field_validator("keywords")
    @classmethod
    def keywords_max_20(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("subtopic cannot have more than 20 keywords")
        return v

    @field_validator("keywords")
    @classmethod
    def keywords_non_empty_strings(cls, v: list[str]) -> list[str]:
        for kw in v:
            if not kw.strip():
                raise ValueError("keyword must not be empty or whitespace")
        return v


class ClusterModel(BaseModel):
    """A topic cluster with its subtopics."""

    name: str = Field(..., min_length=1, description="Cluster name")
    subtopics: list[SubtopicModel] = Field(
        ...,
        min_length=1,
        description="1–10 subtopics",
    )

    @field_validator("subtopics")
    @classmethod
    def subtopics_max_10(cls, v: list[SubtopicModel]) -> list[SubtopicModel]:
        if len(v) > 10:
            raise ValueError("cluster cannot have more than 10 subtopics")
        return v


class ParsedCluster(BaseModel):
    """The full cluster configuration — top-level validated model."""

    pillar: str = Field(..., min_length=1, description="Pillar name")
    clusters: list[ClusterModel] = Field(..., min_length=1, description="1+ clusters")

    @model_validator(mode="after")
    def validate_total_subtopics(self) -> "ParsedCluster":
        total = sum(len(c.subtopics) for c in self.clusters)
        if total == 0:
            raise ValueError("cluster config must have at least one subtopic")
        return self

    @property
    def all_subtopics(self) -> list[tuple[str, str, SubtopicModel]]:
        """Return all subtopics as (pillar, cluster_name, subtopic) tuples."""
        result = []
        for cluster in self.clusters:
            for subtopic in cluster.subtopics:
                result.append((self.pillar, cluster.name, subtopic))
        return result


def parse_cluster(raw: dict) -> ParsedCluster:
    """
    Parse and validate a raw cluster dict into a ParsedCluster.

    Raises pydantic.ValidationError on invalid input.
    """
    return ParsedCluster.model_validate(raw)
