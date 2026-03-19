# Reconciliation Report: `soft-cases-mvp-plan.md` vs Actual Build

**Date:** 10 Mar 2026  
**Source directive:** `docs/soft-cases-mvp-plan.md`  
**Compared against:** current `soft-cases` codebase on `main`

---

## Decision 1: Standalone Service Architecture

**IMPLEMENTED**

| Requirement | Status | Evidence |
|---|---|---|
| Build as a standalone service first (not inside ACL yet) | IMPLEMENTED | Separate `soft-cases/backend` and `soft-cases/frontend` projects |
| Keep migration path to ACL clear | IMPLEMENTED | Namespace is `citation_intel`; DB tables are `ci_*` to avoid collisions |
| Preserve eventual merge into ACL | IMPLEMENTED | Module layout mirrors ACL patterns (FastAPI + SQLAlchemy + Alembic + Next.js) |

---

## Decision 2: Citation Intelligence Pipeline

**IMPLEMENTED**

| Requirement | Status | Evidence |
|---|---|---|
| Multi-stage pipeline (synthesise, discover, dedup, score, complete) | IMPLEMENTED | `backend/app/citation_intel/pipeline/orchestrator.py` |
| Query synthesis from cluster JSON | IMPLEMENTED | `query_synthesiser.py` + parser validations in `cluster_parser.py` |
| Perplexity + Semantic Scholar + arXiv services | IMPLEMENTED | `services/perplexity.py`, `services/semantic_scholar.py`, `services/arxiv.py` |
| Dedup and classify before scoring | IMPLEMENTED | `pipeline/deduplicator.py`, `pipeline/classifier.py` |
| Authority scoring and normalisation | IMPLEMENTED | `scoring/scorer.py`, `scoring/normaliser.py` |

---

## Decision 3: Backend API Surface

**IMPLEMENTED**

| Requirement | Status | Evidence |
|---|---|---|
| Health endpoint | IMPLEMENTED | `GET /api/v1/health` in `citation_intel/router.py` |
| Cluster CRUD-lite (create/list/get) | IMPLEMENTED | `POST /clusters`, `GET /clusters`, `GET /clusters/{id}` |
| Run creation and status endpoints | IMPLEMENTED | `POST /runs`, `GET /runs`, `GET /runs/{id}`, `GET /runs/{id}/jobs` |
| Filter/sort/paginate results endpoint | IMPLEMENTED | `GET /runs/{id}/results` |
| CSV and JSON export | IMPLEMENTED | `GET /runs/{id}/export/csv`, `GET /runs/{id}/export/json` |

---

## Decision 4: Frontend Screens

**IMPLEMENTED**

| Requirement | Status | Evidence |
|---|---|---|
| Screen 1 query configuration | IMPLEMENTED | `frontend/app/page.tsx` |
| Screen 2 run progress | IMPLEMENTED | `frontend/app/runs/[id]/page.tsx` |
| Screen 3 results table | IMPLEMENTED | `frontend/app/runs/[id]/results/page.tsx` |
| Table filtering/sorting/pagination + export actions | IMPLEMENTED | Results page wiring and API integration complete |

---

## Decision 5: Database Schema (`ci_*`)

**IMPLEMENTED (with post-build fix)**

| Requirement | Status | Evidence |
|---|---|---|
| Initial schema migration for CI tables | IMPLEMENTED | `backend/alembic/versions/001_citation_intel_tables.py` |
| Track arXiv categories in scored rows | **FIXED post-build** | `002_add_arxiv_categories_to_ci_scored_results.py` + model update |

---

## Decision 6: Runtime Reliability + Crash Recovery

**IMPLEMENTED**

| Requirement | Status | Evidence |
|---|---|---|
| Stale run recovery at startup | IMPLEMENTED | `backend/app/main.py` lifespan updates stale runs to `failed` |
| CORS config with environment handling | IMPLEMENTED | `backend/app/config.py` `allowed_origins` + dev localhost list |
| Async DB driver conversion from `postgresql://` | IMPLEMENTED | `config.py` `async_database_url` property |

---

## Decision 7: Test-First Safety Gate

**IMPLEMENTED**

| Requirement | Status | Evidence |
|---|---|---|
| Regression tests for discovered breakages before integration | IMPLEMENTED | `backend/app/tests/citation_intel/test_known_bugs.py` |
| Full citation-intel test suite passing before deployment | IMPLEMENTED | Unit/integration coverage across parser, services, dedup, scoring, relevance, and regressions |

---

## Critical Post-Directive Fixes (Bugs Found During Build)

### BUG-1: ORM result serialization broke `/runs/{id}/results`
- Added `ScoredResultResponse` with `from_attributes=True`
- Added `response_model=list[ScoredResultResponse]` to endpoint
- Added missing ORM field `arxiv_categories` and migration 002

### BUG-2: `filter_config.min_topical_relevance` was ignored
- Added new module `pipeline/filter.py`
- Wired `apply_filter_config_gate()` into orchestrator after scoring

### BUG-3: Results pagination disabled incorrectly in frontend
- Fixed next-page disabled condition to use raw API page size (`results.length < 50`)

### BUG-4: Duplicate run start race
- Added explicit `/runs/{run_id}/start` semantics and conflict handling around queued state

### BUG-5: `fallback_raw_id` could attach scored rows to wrong raw row
- Removed fallback behavior
- Orchestrator now skips records that cannot map to a canonical raw result id

### BUG-6: Pydantic private attrs in normaliser path
- Declared `_velocity_norm` and `_influential_norm` as `PrivateAttr`
- Replaced `object.__setattr__` usage with direct assignment

### BUG-7: Score breakdown mismatch for preprints
- Corrected handling and persistence path for preprint score inputs

### BUG-8: Frontend crash on malformed result URLs
- Wrapped hostname extraction in `try/catch`
- Falls back to plain text rendering for invalid URLs

---

## Explicitly Deferred (By Design)

| Item | Deferred To |
|---|---|
| Claim extraction + claim set creation | ACL integration step (Step 5) |
| `claim_sets` table in live ACL DB | Step 4/5 decision gate |
| "Send to VEP" action from results | Step 5d |
| Retirement of standalone services | Step 6 |

---

## Post-MVP UX Enhancement: Novice Cluster Generation

**IMPLEMENTED**

| Requirement | Status | Evidence |
|---|---|---|
| Add novice topic input path on source discovery page | IMPLEMENTED | `frontend/app/page.tsx` adds topic input + generate action |
| Generate stage-1-style cluster drafts via OpenAI | IMPLEMENTED | `POST /api/v1/clusters/generate` in `backend/app/citation_intel/router.py` |
| Keep expert JSON flow intact | IMPLEMENTED | Existing JSON editor and `Load example` path unchanged |
| Re-validate generated JSON against strict parser before use | IMPLEMENTED | `parse_cluster(...)` called server-side before returning generated config |

This enhancement lowers onboarding friction for non-expert users while preserving strict schema safety for the existing run pipeline.

---

## Summary

| Area | Status |
|---|---|
| Core MVP pipeline | IMPLEMENTED |
| Backend API + exports | IMPLEMENTED |
| Frontend 3-screen workflow | IMPLEMENTED |
| Regression bugfixes (1-8) | IMPLEMENTED |
| Railway deployment hardening | IN PROGRESS |
| ACL merge work (Step 5) | NOT STARTED |

Soft-cases is build-complete as a standalone service and ready for Step 3 smoke testing once Railway deployment is fully green.
