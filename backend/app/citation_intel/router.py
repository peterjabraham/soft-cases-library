"""
Citation Intelligence API router.

Endpoints:
  GET  /health
  POST /clusters           — save a cluster config
  GET  /clusters           — list saved clusters
  GET  /clusters/{id}      — get cluster by id
  POST /runs               — start a discovery run
  GET  /runs               — list runs
  GET  /runs/{id}          — run status
  GET  /runs/{id}/jobs     — per-source job status
  GET  /runs/{id}/results  — scored results (paginated, filterable)
  GET  /runs/{id}/export/csv
  GET  /runs/{id}/export/json
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.citation_intel.cluster_parser import ParsedCluster, parse_cluster
from app.config import get_settings
from app.database import get_db
from app.models.ci_models import CICluster, CIRun

logger = structlog.get_logger()

router = APIRouter(tags=["citation-intelligence"])


# ── Scored result response schema ───────────────────────────────────────────

class ScoredResultResponse(BaseModel):
    id: str
    run_id: str
    raw_result_id: str
    content_type: str
    url: Optional[str]
    doi: Optional[str]
    arxiv_id: Optional[str]
    title: Optional[str]
    authors: Optional[list[str]]
    abstract_or_snippet: Optional[str]
    published_date: Optional[str]
    venue: Optional[str]
    source_tier: Optional[int]
    tier_multiplier: Optional[float]
    pillar: Optional[str]
    cluster_name: Optional[str]
    subtopic: Optional[str]
    matched_keywords: Optional[list[str]]
    keyword_density: Optional[float]
    topical_relevance: Optional[float]
    citation_count: Optional[int]
    citation_velocity: Optional[float]
    influential_citations: Optional[int]
    venue_tier: Optional[int]
    is_preprint: bool
    arxiv_categories: Optional[list[str]]
    category_tier: Optional[int]
    raw_score: Optional[float]
    final_score: Optional[float]
    score_confidence: Optional[int]
    excluded: bool
    excluded_reason: Optional[str]
    discovered_by: Optional[list[str]]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Health ─────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok", "service": "soft-cases", "version": "0.1.0"}


# ── Cluster schemas ─────────────────────────────────────────────────────────

class ClusterCreateRequest(BaseModel):
    name: str
    cluster_config: dict


class ClusterGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200)


class ClusterResponse(BaseModel):
    id: str
    name: str
    cluster_config: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ClusterGenerateResponse(BaseModel):
    cluster_config: dict
    model: str
    usage: Optional[dict] = None


# ── Cluster endpoints ───────────────────────────────────────────────────────

@router.post("/clusters", response_model=ClusterResponse, status_code=201)
async def create_cluster(body: ClusterCreateRequest, db: AsyncSession = Depends(get_db)):
    """Save a cluster configuration for reuse across runs."""
    # Validate the cluster config shape
    try:
        parse_cluster(body.cluster_config)
    except (ValidationError, Exception) as e:
        raise HTTPException(status_code=422, detail=f"Invalid cluster config: {e}")

    cluster = CICluster(
        name=body.name,
        cluster_config=body.cluster_config,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(cluster)
    await db.commit()
    await db.refresh(cluster)
    return cluster


@router.post("/clusters/generate", response_model=ClusterGenerateResponse)
async def generate_cluster(body: ClusterGenerateRequest):
    """Generate a novice-friendly cluster config from a plain-language topic."""
    from app.citation_intel.services.openai_cluster_gen import generate_cluster_config

    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI cluster generation is not configured (missing OPENAI_API_KEY)",
        )

    topic = body.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Topic cannot be empty")

    try:
        generated = await generate_cluster_config(
            topic=topic,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        # Re-validate against the strict parser used by run creation.
        parse_cluster(generated.cluster_config)
    except httpx.HTTPStatusError as e:
        msg = "OpenAI request failed"
        try:
            provider_detail = e.response.json()
            if isinstance(provider_detail, dict):
                msg = provider_detail.get("error", {}).get("message", msg)
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"Cluster generation failed: {msg}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Cluster generation failed: {str(e)}")
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Generated cluster failed schema validation: {str(e)}",
        )
    except Exception as e:
        logger.exception("cluster_generate_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Cluster generation failed unexpectedly")

    return ClusterGenerateResponse(
        cluster_config=generated.cluster_config,
        model=generated.model,
        usage=generated.usage,
    )


@router.get("/clusters", response_model=list[ClusterResponse])
async def list_clusters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CICluster).order_by(CICluster.created_at.desc()).limit(50)
    )
    return result.scalars().all()


@router.get("/clusters/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(cluster_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CICluster).where(CICluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


# ── Run schemas ─────────────────────────────────────────────────────────────

class RunCreateRequest(BaseModel):
    cluster_config: dict
    cluster_id: Optional[str] = None
    source_config: dict = {
        "perplexity": True,
        "semantic_scholar": True,
        "arxiv": True,
    }
    filter_config: Optional[dict] = None


class RunResponse(BaseModel):
    id: str
    status: str
    cluster_config: dict
    source_config: dict
    filter_config: Optional[dict]
    total_discovered: Optional[int]
    total_deduped: Optional[int]
    total_scored: Optional[int]
    subtopic_relevance_scores: Optional[dict]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Run endpoints ────────────────────────────────────────────────────────────

@router.post("/runs", response_model=RunResponse, status_code=201)
async def create_run(
    body: RunCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create a discovery run and immediately queue the pipeline."""
    from app.citation_intel.pipeline.orchestrator import run_pipeline

    try:
        parsed = parse_cluster(body.cluster_config)
    except (ValidationError, Exception) as e:
        raise HTTPException(status_code=422, detail=f"Invalid cluster config: {e}")

    run = CIRun(
        cluster_id=body.cluster_id,
        status="queued",
        cluster_config=body.cluster_config,
        source_config=body.source_config,
        filter_config=body.filter_config,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    logger.info("run_created", run_id=run.id, subtopics=len(parsed.all_subtopics))
    background_tasks.add_task(run_pipeline, run.id)

    return run


@router.post("/runs/{run_id}/start", response_model=RunResponse)
async def start_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger a queued run.

    Useful if the background task was lost (e.g. server restart) or
    the run was created before the orchestrator existed.
    Returns 409 if the run is not in 'queued' state.
    """
    from app.citation_intel.pipeline.orchestrator import run_pipeline

    result = await db.execute(select(CIRun).where(CIRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "queued":
        raise HTTPException(
            status_code=409,
            detail=f"Run is '{run.status}' — only queued runs can be started",
        )

    background_tasks.add_task(run_pipeline, run.id)
    logger.info("run_manually_started", run_id=run.id)
    return run


@router.get("/runs", response_model=list[RunResponse])
async def list_runs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page
    result = await db.execute(
        select(CIRun).order_by(CIRun.created_at.desc()).offset(offset).limit(per_page)
    )
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CIRun).where(CIRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/jobs")
async def get_run_jobs(run_id: str, db: AsyncSession = Depends(get_db)):
    """Per-source job status for the pipeline progress screen."""
    from app.models.ci_models import CIQueryJob

    result = await db.execute(
        select(CIQueryJob)
        .where(CIQueryJob.run_id == run_id)
        .order_by(CIQueryJob.created_at)
    )
    jobs = result.scalars().all()
    return [
        {
            "id": j.id,
            "subtopic": j.subtopic,
            "source_api": j.source_api,
            "status": j.status,
            "items_returned": j.items_returned,
            "error_message": j.error_message,
            "retries": j.retries,
        }
        for j in jobs
    ]


@router.get("/runs/{run_id}/results", response_model=list[ScoredResultResponse])
async def get_run_results(
    run_id: str,
    content_type: Optional[str] = None,
    min_score: Optional[float] = Query(None, ge=0, le=100),
    source_tier: Optional[str] = None,
    subtopic: Optional[str] = None,
    sort: str = Query("final_score", pattern="^(final_score|citation_count|published_date|topical_relevance)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Scored results with filtering, sorting, and pagination."""
    from app.models.ci_models import CIScoredResult
    from sqlalchemy import asc, desc

    q = select(CIScoredResult).where(
        CIScoredResult.run_id == run_id,
        CIScoredResult.excluded == False,  # noqa: E712
    )

    if content_type:
        q = q.where(CIScoredResult.content_type == content_type)
    if min_score is not None:
        q = q.where(CIScoredResult.final_score >= min_score)
    if subtopic:
        q = q.where(CIScoredResult.subtopic == subtopic)
    if source_tier:
        tiers = [int(t) for t in source_tier.split(",") if t.strip().isdigit()]
        if tiers:
            q = q.where(CIScoredResult.source_tier.in_(tiers))

    sort_col = getattr(CIScoredResult, sort, CIScoredResult.final_score)
    q = q.order_by(desc(sort_col) if order == "desc" else asc(sort_col))
    q = q.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(q)
    items = result.scalars().all()
    return items


@router.get("/runs/{run_id}/export/csv")
async def export_csv(run_id: str, db: AsyncSession = Depends(get_db)):
    """Download all scored results (including excluded) as CSV."""
    import csv
    import io
    from app.models.ci_models import CIScoredResult

    result = await db.execute(
        select(CIScoredResult)
        .where(CIScoredResult.run_id == run_id)
        .order_by(CIScoredResult.final_score.desc().nulls_last())
    )
    items = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "title", "url", "doi", "arxiv_id", "content_type", "venue",
        "published_date", "source_tier", "tier_multiplier",
        "pillar", "cluster_name", "subtopic", "matched_keywords",
        "topical_relevance", "keyword_density",
        "citation_count", "citation_velocity", "influential_citations",
        "venue_tier", "is_preprint", "category_tier",
        "raw_score", "final_score", "score_confidence",
        "excluded", "excluded_reason", "discovered_by",
    ])
    for item in items:
        writer.writerow([
            item.title, item.url, item.doi, item.arxiv_id,
            item.content_type, item.venue, item.published_date,
            item.source_tier, item.tier_multiplier,
            item.pillar, item.cluster_name, item.subtopic,
            "|".join(item.matched_keywords or []),
            item.topical_relevance, item.keyword_density,
            item.citation_count, item.citation_velocity, item.influential_citations,
            item.venue_tier, item.is_preprint, item.category_tier,
            item.raw_score, item.final_score, item.score_confidence,
            item.excluded, item.excluded_reason,
            "|".join(item.discovered_by or []),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=run_{run_id[:8]}_results.csv"},
    )


@router.get("/runs/{run_id}/export/json")
async def export_json(run_id: str, db: AsyncSession = Depends(get_db)):
    """Download all scored results as JSON."""
    import json
    from app.models.ci_models import CIScoredResult

    result = await db.execute(
        select(CIScoredResult)
        .where(CIScoredResult.run_id == run_id)
        .order_by(CIScoredResult.final_score.desc().nulls_last())
    )
    items = result.scalars().all()

    data = [
        {
            "title": i.title, "url": i.url, "doi": i.doi, "arxiv_id": i.arxiv_id,
            "content_type": i.content_type, "venue": i.venue,
            "published_date": i.published_date,
            "source_tier": i.source_tier, "tier_multiplier": i.tier_multiplier,
            "pillar": i.pillar, "cluster_name": i.cluster_name, "subtopic": i.subtopic,
            "matched_keywords": i.matched_keywords,
            "topical_relevance": i.topical_relevance, "keyword_density": i.keyword_density,
            "citation_count": i.citation_count, "citation_velocity": i.citation_velocity,
            "influential_citations": i.influential_citations,
            "venue_tier": i.venue_tier, "is_preprint": i.is_preprint,
            "category_tier": i.category_tier,
            "raw_score": i.raw_score, "final_score": i.final_score,
            "score_confidence": i.score_confidence,
            "excluded": i.excluded, "excluded_reason": i.excluded_reason,
            "discovered_by": i.discovered_by,
        }
        for i in items
    ]

    return StreamingResponse(
        iter([json.dumps(data, default=str, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=run_{run_id[:8]}_results.json"},
    )
