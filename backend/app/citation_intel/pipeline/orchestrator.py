"""
Citation Intelligence pipeline orchestrator.

State machine:
  queued → synthesising → discovering → deduplicating → scoring → complete
  any stage on unhandled exception → failed

Called as a FastAPI BackgroundTask immediately after POST /runs.
Each job runs in its own DB session to avoid concurrent session conflicts.
"""

from __future__ import annotations

import asyncio
import traceback
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.citation_intel.cluster_parser import parse_cluster
from app.citation_intel.pipeline.classifier import classify_batch
from app.citation_intel.pipeline.deduplicator import deduplicate
from app.citation_intel.pipeline.raw_result import RawResultData
from app.citation_intel.query_synthesiser import synthesise_all_queries
from app.citation_intel.scoring.normaliser import normalise_citation_signals
from app.citation_intel.scoring.scorer import score
from app.citation_intel.services import arxiv as svc_arxiv
from app.citation_intel.services import perplexity as svc_perplexity
from app.citation_intel.services import semantic_scholar as svc_ss
from app.config import get_settings
from app.database import async_session_factory
from app.models.ci_models import CIQueryJob, CIRawResult, CIRun, CIScoredResult

logger = structlog.get_logger()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _find_cluster_name(cluster_config: dict, subtopic_name: str) -> str:
    for cluster in cluster_config.get("clusters", []):
        for sub in cluster.get("subtopics", []):
            if sub.get("name") == subtopic_name:
                return cluster.get("name", "")
    return ""


async def _set_status(db: AsyncSession, run: CIRun, status: str, **extras) -> None:
    run.status = status
    run.updated_at = _now()
    for k, v in extras.items():
        setattr(run, k, v)
    await db.commit()


async def _fail_run(db: AsyncSession, run: CIRun, error: str) -> None:
    logger.error("run_failed", run_id=run.id, error=error[:300])
    await _set_status(db, run, "failed", error_message=error[:2000])


# ── Per-job execution ────────────────────────────────────────────────────────

async def _execute_job(
    job_id: str,
    run_id: str,
    cluster_config: dict,
    sems: dict[str, asyncio.Semaphore],
    http_client: httpx.AsyncClient,
) -> list[RawResultData]:
    """
    Execute a single query job.

    Opens its own DB session so multiple jobs can run concurrently
    without competing on a shared session connection.
    Updates job.status live (queued → running → complete/failed).
    Persists CIRawResult rows and returns the in-memory RawResultData list.
    """
    settings = get_settings()

    async with async_session_factory() as db:
        res = await db.execute(select(CIQueryJob).where(CIQueryJob.id == job_id))
        job = res.scalar_one_or_none()
        if not job:
            logger.error("job_not_found", job_id=job_id)
            return []

        pillar = cluster_config.get("pillar", "")
        cluster_name = _find_cluster_name(cluster_config, job.subtopic)
        log = logger.bind(job_id=job_id, api=job.source_api, subtopic=job.subtopic)

        job.status = "running"
        await db.commit()

        try:
            if job.source_api == "perplexity":
                raw = await svc_perplexity.discover(
                    query_text=job.query_text,
                    subtopic=job.subtopic,
                    pillar=pillar,
                    cluster_name=cluster_name,
                    api_key=settings.perplexity_api_key,
                    semaphore=sems["perplexity"],
                    client=http_client,
                )
            elif job.source_api == "semantic_scholar":
                _max, _sleep = settings.semantic_scholar_rate_limit
                raw = await svc_ss.discover(
                    query_text=job.query_text,
                    subtopic=job.subtopic,
                    pillar=pillar,
                    cluster_name=cluster_name,
                    api_key=settings.semantic_scholar_api_key,
                    semaphore=sems["semantic_scholar"],
                    sleep_between=_sleep,
                    client=http_client,
                )
            elif job.source_api == "arxiv":
                raw = await svc_arxiv.discover(
                    query_text=job.query_text,
                    subtopic=job.subtopic,
                    pillar=pillar,
                    cluster_name=cluster_name,
                    semaphore=sems["arxiv"],
                    client=http_client,
                )
            else:
                log.warning("unknown_source_api", source_api=job.source_api)
                raw = []

            for r in raw:
                db.add(CIRawResult(
                    run_id=run_id,
                    job_id=job_id,
                    source_api=r.source_api,
                    content_type=r.content_type,
                    url=r.url,
                    doi=r.doi,
                    arxiv_id=r.arxiv_id,
                    title=r.title,
                    authors=r.authors or [],
                    abstract_or_snippet=r.abstract_or_snippet,
                    published_date=r.published_date,
                    venue=r.venue,
                    raw_payload=r.raw_payload,
                    dedup_key=r.dedup_key,
                    is_duplicate=False,
                    created_at=_now(),
                ))

            job.status = "complete"
            job.items_returned = len(raw)
            await db.commit()

            log.info("job_complete", items=len(raw))
            return raw

        except Exception as exc:
            err = str(exc)
            log.error("job_failed", error=err)
            job.status = "failed"
            job.error_message = err[:500]
            await db.commit()
            return []


# ── Main entry point ─────────────────────────────────────────────────────────

async def run_pipeline(run_id: str) -> None:
    """
    Top-level pipeline entry point.

    Called as a FastAPI BackgroundTask after POST /runs or POST /runs/{id}/start.
    Creates its own DB session — independent of the request/response lifecycle.
    """
    log = logger.bind(run_id=run_id)

    async with async_session_factory() as db:
        result = await db.execute(select(CIRun).where(CIRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            log.error("run_not_found")
            return

        if run.status not in ("queued",):
            log.warning("run_already_processing", status=run.status)
            return

        try:
            await _pipeline_inner(db, run, log)
        except Exception as exc:
            tb = traceback.format_exc()
            log.error("pipeline_unhandled", error=str(exc), traceback=tb[:500])
            await _fail_run(db, run, f"{exc}\n\n{tb}"[:2000])


# ── Pipeline stages ───────────────────────────────────────────────────────────

async def _pipeline_inner(db: AsyncSession, run: CIRun, log) -> None:  # noqa: ANN001
    settings = get_settings()

    # ── Stage 1: SYNTHESISING ─────────────────────────────────────────────────
    await _set_status(db, run, "synthesising", started_at=_now())
    log.info("stage_synthesising")

    parsed = parse_cluster(run.cluster_config)

    if not parsed.all_subtopics:
        await _fail_run(db, run, "Cluster config contains no subtopics")
        return

    # Build query jobs: subtopic × source × query_text
    job_records: list[CIQueryJob] = []
    for pillar, cluster_name, sub in parsed.all_subtopics:
        tagged = synthesise_all_queries(
            pillar=pillar,
            cluster_name=cluster_name,
            subtopic=sub,
        )
        for api_name in ("perplexity", "semantic_scholar", "arxiv"):
            if not run.source_config.get(api_name, False):
                continue
            for tq in tagged:
                job = CIQueryJob(
                    run_id=run.id,
                    subtopic=sub.name,
                    query_text=tq["query_text"],
                    source_api=api_name,
                    status="queued",
                    created_at=_now(),
                )
                db.add(job)
                job_records.append(job)

    await db.commit()
    for j in job_records:
        await db.refresh(j)

    log.info("jobs_created", count=len(job_records))

    # ── Stage 2: DISCOVERING ──────────────────────────────────────────────────
    await _set_status(db, run, "discovering")
    log.info("stage_discovering")

    # Per-run semaphores — different runs don't share rate limits
    ss_max, _ = settings.semantic_scholar_rate_limit
    sems: dict[str, asyncio.Semaphore] = {
        "perplexity": asyncio.Semaphore(1),
        "semantic_scholar": asyncio.Semaphore(ss_max),
        "arxiv": asyncio.Semaphore(1),
    }

    async with httpx.AsyncClient(timeout=45.0) as http_client:
        gathered = await asyncio.gather(
            *[
                _execute_job(j.id, run.id, run.cluster_config, sems, http_client)
                for j in job_records
            ],
            return_exceptions=True,
        )

    all_raw: list[RawResultData] = []
    for item in gathered:
        if isinstance(item, Exception):
            log.error("job_gather_exception", error=str(item))
        elif isinstance(item, list):
            all_raw.extend(item)

    log.info("discovery_complete", raw=len(all_raw))

    if not all_raw:
        await _fail_run(
            db, run,
            "All discovery jobs returned no results. "
            "Check API keys and network connectivity.",
        )
        return

    # ── Stage 3: DEDUPLICATING ────────────────────────────────────────────────
    await _set_status(db, run, "deduplicating", total_discovered=len(all_raw))
    log.info("stage_deduplicating")

    deduped = deduplicate(all_raw)
    classify_batch(deduped)
    unique = [r for r in deduped if not r.is_duplicate]

    log.info("dedup_complete", unique=len(unique), dupes=len(all_raw) - len(unique))

    # ── Stage 4: SCORING ──────────────────────────────────────────────────────
    await _set_status(db, run, "scoring", total_deduped=len(unique))
    log.info("stage_scoring")

    subtopic_keywords: dict[str, list[str]] = {
        sub.name: sub.keywords
        for _, _, sub in parsed.all_subtopics
    }

    normalise_citation_signals(unique)

    for r in unique:
        kws = subtopic_keywords.get(r.subtopic, [])
        score(r, kws)

    # Aggregate mean topical relevance per subtopic for the run summary
    rel_acc: dict[str, list[float]] = {}
    for r in unique:
        if r.subtopic and r.topical_relevance is not None:
            rel_acc.setdefault(r.subtopic, []).append(r.topical_relevance)
    subtopic_rel_map = {
        st: round(sum(vs) / len(vs), 4)
        for st, vs in rel_acc.items() if vs
    }

    # Look up CIRawResult IDs for the scored result FK
    rr_rows = await db.execute(
        select(CIRawResult).where(CIRawResult.run_id == run.id)
    )
    rr_list: list[CIRawResult] = list(rr_rows.scalars().all())

    # Build lookup keyed on the first non-null identity field
    rr_lookup: dict[str, str] = {}
    for rr in rr_list:
        key = rr.doi or rr.arxiv_id or rr.url
        if key and key not in rr_lookup:
            rr_lookup[key] = rr.id
    fallback_raw_id = rr_list[0].id if rr_list else None

    stored = 0
    for r in unique:
        identity_key = r.doi or r.arxiv_id or r.url
        raw_id = (rr_lookup.get(identity_key) if identity_key else None) or fallback_raw_id
        if not raw_id:
            log.warning("skipping_result_no_raw_id", url=r.url)
            continue

        db.add(CIScoredResult(
            run_id=run.id,
            raw_result_id=raw_id,
            content_type=r.content_type,
            url=r.url,
            doi=r.doi,
            arxiv_id=r.arxiv_id,
            title=r.title,
            authors=r.authors or [],
            abstract_or_snippet=r.abstract_or_snippet,
            published_date=r.published_date,
            venue=r.venue,
            source_tier=r.source_tier,
            tier_multiplier=r.tier_multiplier,
            pillar=r.pillar or parsed.pillar,
            cluster_name=r.cluster_name,
            subtopic=r.subtopic,
            matched_keywords=r.matched_keywords or [],
            keyword_density=r.keyword_density,
            topical_relevance=r.topical_relevance,
            citation_count=r.citation_count,
            citation_velocity=r.citation_velocity,
            influential_citations=r.influential_citations,
            venue_tier=r.venue_tier,
            is_preprint=r.is_preprint,
            category_tier=r.category_tier,
            raw_score=r.raw_score,
            final_score=r.final_score,
            score_confidence=r.score_confidence,
            excluded=r.excluded,
            excluded_reason=r.excluded_reason,
            discovered_by=r.discovered_by or [r.source_api],
            created_at=_now(),
        ))
        stored += 1

    # ── Stage 5: COMPLETE ─────────────────────────────────────────────────────
    await _set_status(
        db, run, "complete",
        total_scored=stored,
        subtopic_relevance_scores=subtopic_rel_map,
        completed_at=_now(),
    )
    log.info("pipeline_complete", scored=stored)
