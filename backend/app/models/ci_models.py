"""
Citation Intelligence SQLAlchemy models.

All tables prefixed ci_ to avoid collisions when this service
eventually merges into ai-library.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class CICluster(TimestampMixin, Base):
    """
    Saved cluster configurations — reused across runs.

    cluster_config: full hierarchical JSON
    { "pillar": "...", "clusters": [{ "name": "...", "subtopics": [...] }] }
    """
    __tablename__ = "ci_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cluster_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    runs: Mapped[list["CIRun"]] = relationship(back_populates="cluster")


class CIRun(TimestampMixin, Base):
    """
    One record per discovery pipeline execution.

    updated_at doubles as heartbeat — stale threshold: 30 minutes.
    Status machine: queued → synthesising → discovering → deduplicating → scoring → complete
    Failure branch: any state → failed
    """
    __tablename__ = "ci_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    cluster_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ci_clusters.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    cluster_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    filter_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    total_discovered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_deduped: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_scored: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subtopic_relevance_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cluster: Mapped["CICluster | None"] = relationship(back_populates="runs")
    query_jobs: Mapped[list["CIQueryJob"]] = relationship(back_populates="run")
    raw_results: Mapped[list["CIRawResult"]] = relationship(back_populates="run")
    scored_results: Mapped[list["CIScoredResult"]] = relationship(back_populates="run")


class CIQueryJob(Base):
    """
    One row per API query (subtopic × source_api).
    Enables per-source progress display on the pipeline screen.
    """
    __tablename__ = "ci_query_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("ci_runs.id"), nullable=False)
    subtopic: Mapped[str] = mapped_column(String(300), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_api: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    items_returned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    run: Mapped["CIRun"] = relationship(back_populates="query_jobs")
    raw_results: Mapped[list["CIRawResult"]] = relationship(back_populates="job")


class CIRawResult(Base):
    """
    One row per discovered item, before dedup and scoring.
    Preserves which API found each item.
    """
    __tablename__ = "ci_raw_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("ci_runs.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ci_query_jobs.id"), nullable=False
    )
    source_api: Mapped[str] = mapped_column(String(50), nullable=False)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    arxiv_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    abstract_or_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    run: Mapped["CIRun"] = relationship(back_populates="raw_results")
    job: Mapped["CIQueryJob"] = relationship(back_populates="raw_results")
    scored_result: Mapped["CIScoredResult | None"] = relationship(
        back_populates="raw_result"
    )


class CIScoredResult(Base):
    """
    One row per unique, scored result. This is what the UI displays.
    """
    __tablename__ = "ci_scored_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("ci_runs.id"), nullable=False)
    raw_result_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ci_raw_results.id"), nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    arxiv_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    abstract_or_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tier_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    pillar: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cluster_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    subtopic: Mapped[str | None] = mapped_column(String(300), nullable=True)
    matched_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    keyword_density: Mapped[float | None] = mapped_column(Float, nullable=True)
    topical_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    citation_velocity: Mapped[float | None] = mapped_column(Float, nullable=True)
    influential_citations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_preprint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excluded_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    discovered_by: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    run: Mapped["CIRun"] = relationship(back_populates="scored_results")
    raw_result: Mapped["CIRawResult"] = relationship(back_populates="scored_result")
