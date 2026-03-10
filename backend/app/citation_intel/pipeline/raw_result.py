"""
RawResultData — in-memory Pydantic model that flows through the pipeline.

Separate from the SQLAlchemy CIRawResult model to keep pipeline logic
decoupled from the database layer.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, PrivateAttr


class RawResultData(BaseModel):
    """Mutable in-memory record produced by discovery services."""

    # Source
    source_api: str  # "perplexity" | "semantic_scholar" | "arxiv"
    subtopic: str = ""
    pillar: str = ""
    cluster_name: str = ""

    # Identity
    url: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None

    # Metadata
    title: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    abstract_or_snippet: Optional[str] = None
    published_date: Optional[str] = None
    venue: Optional[str] = None
    arxiv_categories: list[str] = Field(default_factory=list)

    # Citation signals (Semantic Scholar only)
    citation_count: Optional[int] = None
    recent_citations: Optional[int] = None  # last 12 months
    influential_citations: Optional[int] = None

    # Classification (set by classifier)
    content_type: str = "unknown"  # "academic" | "news" | "blog" | "unknown"
    source_tier: Optional[int] = None
    tier_multiplier: Optional[float] = None
    category_tier: Optional[int] = None
    venue_tier: Optional[int] = None
    is_preprint: bool = False

    # Dedup (set by deduplicator)
    dedup_key: Optional[str] = None
    is_duplicate: bool = False
    discovered_by: list[str] = Field(default_factory=list)

    # Scoring (set by scorer)
    matched_keywords: list[str] = Field(default_factory=list)
    keyword_density: Optional[float] = None
    topical_relevance: Optional[float] = None
    citation_velocity: Optional[float] = None
    raw_score: Optional[float] = None
    final_score: Optional[float] = None
    score_confidence: Optional[int] = None
    excluded: bool = False
    excluded_reason: Optional[str] = None

    # Raw payload for debugging
    raw_payload: Optional[dict] = None

    # Normalised citation signals — set by normaliser, consumed by scorer.
    # Declared as PrivateAttr so Pydantic manages them correctly.
    _velocity_norm: float = PrivateAttr(default=0.0)
    _influential_norm: float = PrivateAttr(default=0.0)

    model_config = {"arbitrary_types_allowed": True}
