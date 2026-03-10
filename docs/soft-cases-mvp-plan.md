# Soft-Cases MVP — Citation Intelligence Discovery
## Build-Ready Plan

**Version:** 0.2 (build-ready)
**Date:** 4 March 2026
**Status:** Approved for build
**Location:** `value-lab-platform/soft-cases/` (new standalone service)
**Integration target:** `ai-library/` (Phase 1 of Case Library Restructure)

---

## 1. What We're Building

A **source discovery and authority scoring pipeline** that finds authoritative content on a given topic — analytical claims, principles, expert recommendations — scores each result for authority, and presents ranked results in a full query configuration UI.

This is the "Citation Intelligence" layer: the discovery engine that will feed the Claim Set ingestion pipeline once VEP extraction is added in the Case Library Restructure.

### MVP Scope

**Does:** Query 3 APIs in parallel for a topic cluster, deduplicate results, score authority, present filterable/sortable results table, export CSV/JSON.

**Does not:** Extract claims from discovered sources, create Claim Sets, build relationship records. Those are Phase 1+ of the restructure plan.

### First Test Case

Topic: **"Prompt Injection"** — expects to surface Simon Willison's series (simonwillison.net/series/prompt-injection/), CaMeL/DeepMind defence papers, academic papers on LLM adversarial attacks.

---

## 2. Build Location

New standalone service at:

```
value-lab-platform/
└── soft-cases/          ← NEW (mirrors ai-library structure)
    ├── backend/
    │   ├── app/
    │   │   ├── citation_intel/   # discovery pipeline
    │   │   ├── api/
    │   │   ├── models/
    │   │   ├── schemas/
    │   │   ├── tests/
    │   │   ├── config.py
    │   │   ├── database.py
    │   │   └── main.py
    │   ├── alembic/
    │   │   └── versions/
    │   ├── requirements.txt
    │   └── pyproject.toml
    ├── frontend/
    │   ├── app/
    │   │   ├── page.tsx          # Screen 1: Query configuration
    │   │   ├── runs/
    │   │   │   └── [id]/
    │   │   │       ├── page.tsx  # Screen 2: Pipeline progress
    │   │   │       └── results/
    │   │   │           └── page.tsx  # Screen 3: Results dataset
    │   │   └── layout.tsx
    │   ├── components/
    │   │   ├── ui/               # Reuse design system tokens from ai-library
    │   │   └── research/
    │   ├── lib/
    │   │   ├── api.ts
    │   │   └── types.ts
    │   └── package.json
    ├── docs/
    │   └── soft-cases-mvp-plan.md  (this file)
    ├── railway.toml
    └── .env.example
```

**Rationale for standalone over embedded in ai-library:**
- MVP proves the pipeline concept before we touch ai-library's existing DB
- Keeps integration risk low (existing ai-library continues to function)
- Clean separation when we do integrate: we know exactly what needs to merge
- Mirrors how every other service in the platform is structured

**Integration path:** When Phase 1 of the Case Library Restructure begins, `soft-cases/backend/app/citation_intel/` merges into `ai-library/backend/app/citation_intel/`, the DB tables migrate into the ai-library database, and the frontend pages move to `ai-library/frontend/app/research/`. The `soft-cases/` folder is retired.

---

## 3. Naming Conventions — Locked

| Canonical name | Also known as | What it is |
|---|---|---|
| **Soft-cases** | — | Service name + feature area |
| **Claim Sets** | Soft-cases (record type) | DB record type for concept-anchored claims (Phase 1 of restructure, not in MVP) |
| **Citation Intelligence** | Authority AI Sources, ARP | The discovery + scoring pipeline (what this MVP builds) |
| **Hard-cases** | Cases | Existing library case studies (org + initiative + evidence) |
| **Claim Relationships** | Connected-cases | Relationship layer between claims (Phase 2 of restructure) |

**Code namespace:** Backend: `citation_intel`. DB tables: `ci_` prefix. Frontend routes: `/` (service root) + `/runs/`.

---

## 4. Resolved Decisions

All five open questions from v0.1 are now resolved:

| Question | Decision |
|---|---|
| Save cluster configs to DB? | **Yes.** Table `ci_clusters`, linked to runs. Avoids re-pasting. Each cluster has a name and JSONB body. |
| Auth on routes? | **Yes.** Same `Authorization: Bearer {token}` pattern as ai-library pipeline page. Token from localStorage for MVP. |
| Daily run limit? | **Yes.** `daily_run_limit: int = 10` in config (lower than ai-library's 20 given API costs). Configurable. |
| Perplexity prompt engineering? | **Tuned during Phase B, not pre-planned.** Document final prompt in `citation_intel/services/perplexity.py` after testing. |
| When to upgrade to embedding-based relevance? | **After 10 runs provide ground truth.** Decision point: if keyword-density relevance scores look wrong on manual review after 10 runs, upgrade. Otherwise defer to Phase 2. |

---

## 5. Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.12 | Matches ai-library for future merge |
| Framework | FastAPI + uvicorn | Matches ai-library |
| Async HTTP | httpx (async) | Already used in ai-library |
| XML parsing | `defusedxml` | Safe arXiv Atom XML parsing |
| Concurrency | `asyncio.TaskGroup` + `asyncio.Semaphore` | Per-API rate limiting without Redis overhead |
| In-memory cache | Python dict with TTL | Cache API responses within a run. Upgrade to Redis if needed at scale. |
| Database | PostgreSQL (SQLAlchemy async + asyncpg) | Matches ai-library |
| Migrations | Alembic | Matches ai-library |
| Validation | Pydantic v2 | Matches ai-library |
| Logging | structlog | Matches ai-library |
| Frontend | Next.js 15 (App Router) + Tailwind v3 | Matches ai-library |
| Testing | pytest + pytest-asyncio + httpx | Matches ai-library |

### New `requirements.txt` additions beyond ai-library baseline

```
defusedxml>=0.7.1          # Safe XML parsing for arXiv Atom feed
```

All other dependencies (`fastapi`, `httpx`, `sqlalchemy`, `anthropic`, `structlog`, etc.) are inherited from the ai-library stack.

---

## 6. Environment Variables

`config.py` follows the ai-library pattern: required vars fail fast, optional vars degrade gracefully.

```python
# === Required ===
database_url: str          # PostgreSQL connection string
auth_secret: str           # HS256 JWT secret (same pattern as ai-library)
perplexity_api_key: str    # Required — Perplexity is primary web discovery source

# === Optional (degrade gracefully if absent) ===
semantic_scholar_api_key: Optional[str]  # Free tier works without key (1 req/sec)
# arXiv: no key needed

# === Optional with defaults ===
daily_run_limit: int = 10
allowed_origins: str = "http://localhost:3000"
env: str = "development"
```

`.env.example`:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/soft_cases
AUTH_SECRET=your-secret-here
PERPLEXITY_API_KEY=pplx-...
SEMANTIC_SCHOLAR_API_KEY=   # Optional — leave blank for free tier
```

---

## 7. Database Schema

Five tables, all `ci_`-prefixed. No dependency on ai-library tables — this is a standalone schema.

### `ci_clusters`
Saved cluster configurations for reuse across runs.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | TEXT | Display name e.g. "Prompt Injection v1" |
| `cluster_config` | JSONB | Full hierarchical cluster JSON |
| `created_by` | TEXT | User token identifier |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `ci_runs`
One record per discovery pipeline execution.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `cluster_id` | UUID FK → ci_clusters | Nullable — inline runs don't reference a saved cluster |
| `status` | TEXT | `queued` `synthesising` `discovering` `deduplicating` `scoring` `complete` `failed` |
| `cluster_config` | JSONB | Snapshot of cluster at run time (cluster may change after) |
| `source_config` | JSONB | `{ "perplexity": true, "semantic_scholar": true, "arxiv": true }` |
| `filter_config` | JSONB | Date range, min score, content type filters |
| `total_discovered` | INT | Raw results before dedup |
| `total_deduped` | INT | After dedup |
| `total_scored` | INT | After relevance gate |
| `subtopic_relevance_scores` | JSONB | Avg relevance per subtopic — cluster drift signal |
| `error_message` | TEXT | Nullable |
| `started_at` | TIMESTAMP | |
| `completed_at` | TIMESTAMP | |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | Heartbeat — stale threshold: 30 min |

### `ci_query_jobs`
One row per API query (subtopic × source_api). Enables per-source progress display.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `run_id` | UUID FK → ci_runs | |
| `subtopic` | TEXT | Subtopic name |
| `query_text` | TEXT | The synthesised search string |
| `source_api` | TEXT | `perplexity` `semantic_scholar` `arxiv` |
| `status` | TEXT | `queued` `running` `done` `failed` `rate_limited` |
| `items_returned` | INT | |
| `error_message` | TEXT | Nullable |
| `retries` | INT | Default 0 |
| `created_at` | TIMESTAMP | |

### `ci_raw_results`
One row per discovered item, pre-dedup. Preserves which API found each item.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `run_id` | UUID FK → ci_runs | |
| `job_id` | UUID FK → ci_query_jobs | |
| `source_api` | TEXT | |
| `content_type` | TEXT | `academic` `news` `blog` `unknown` |
| `url` | TEXT | |
| `doi` | TEXT | Nullable |
| `arxiv_id` | TEXT | Nullable |
| `title` | TEXT | |
| `authors` | TEXT[] | |
| `abstract_or_snippet` | TEXT | Nullable |
| `published_date` | DATE | Nullable |
| `venue` | TEXT | Nullable — journal or conference |
| `raw_payload` | JSONB | Full API response for this item |
| `dedup_key` | TEXT | Normalised URL, DOI, or arxiv_id — used for dedup |
| `is_duplicate` | BOOLEAN | Default false |

### `ci_scored_results`
One row per unique, scored result. This is what the UI displays.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `run_id` | UUID FK → ci_runs | |
| `raw_result_id` | UUID FK → ci_raw_results | Canonical (non-duplicate) record |
| `content_type` | TEXT | |
| `url` | TEXT | |
| `doi` | TEXT | Nullable |
| `arxiv_id` | TEXT | Nullable |
| `title` | TEXT | |
| `authors` | TEXT[] | |
| `abstract_or_snippet` | TEXT | Nullable |
| `published_date` | DATE | Nullable |
| `venue` | TEXT | Nullable |
| `source_tier` | INT | 1-5 |
| `tier_multiplier` | FLOAT | |
| `pillar` | TEXT | |
| `cluster_name` | TEXT | |
| `subtopic` | TEXT | Best-matching subtopic |
| `matched_keywords` | TEXT[] | |
| `keyword_density` | FLOAT | |
| `topical_relevance` | FLOAT | 0-1 |
| `citation_count` | INT | Nullable — SS only |
| `citation_velocity` | FLOAT | Nullable — cites/month last 12mo |
| `influential_citations` | INT | Nullable — SS only |
| `venue_tier` | INT | Nullable — 1-3 |
| `is_preprint` | BOOLEAN | Default false |
| `category_tier` | INT | Nullable — arXiv category tier |
| `raw_score` | FLOAT | 0-100 pre-multiplier |
| `final_score` | FLOAT | 0-100 |
| `score_confidence` | INT | 1-5 |
| `excluded` | BOOLEAN | Default false |
| `excluded_reason` | TEXT | Nullable |
| `discovered_by` | TEXT[] | APIs that surfaced this item |
| `created_at` | TIMESTAMP | |

---

## 8. API Endpoints

Mounted under `/api/v1/` in `main.py`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/clusters` | Save a cluster config |
| `GET` | `/clusters` | List saved clusters |
| `GET` | `/clusters/{id}` | Get cluster by ID |
| `POST` | `/runs` | Start a discovery run |
| `GET` | `/runs` | List runs (paginated, newest first) |
| `GET` | `/runs/{id}` | Run status + summary |
| `GET` | `/runs/{id}/jobs` | Per-source job status |
| `GET` | `/runs/{id}/results` | Scored results (paginated, filterable, sortable) |
| `GET` | `/runs/{id}/export/csv` | Download CSV |
| `GET` | `/runs/{id}/export/json` | Download JSON |

**Results query params:** `?content_type=academic&source_tier=1,2&min_score=40&subtopic=Attack+Vectors&sort=final_score&order=desc&page=1&per_page=50`

---

## 9. Pipeline Implementation

### Module Structure

```
backend/app/citation_intel/
├── __init__.py
├── router.py                    # FastAPI router — mounts all endpoints
├── cluster_parser.py            # Parse + validate cluster JSON → Pydantic models
├── query_synthesiser.py         # Generate 2-3 queries per subtopic
├── services/
│   ├── __init__.py
│   ├── perplexity.py            # POST /chat/completions → parse citation URLs
│   ├── semantic_scholar.py      # GET /paper/search + /paper/{id}/citations
│   └── arxiv.py                 # GET export.arxiv.org/api/query (Atom XML)
├── dedup.py                     # URL normalisation, DOI matching, arXiv↔SS merge
├── classifier.py                # Content type + source tier by domain rules
├── data/
│   └── source_tiers.json        # Domain → tier mapping (manually maintained)
├── scoring/
│   ├── __init__.py
│   ├── academic.py              # Full citation formula + preprint formula
│   ├── web.py                   # Web content scoring (limited signals in MVP)
│   └── normalise.py             # Percentile ranking within content type buckets
└── pipeline.py                  # Orchestrator: Stages 1→5 as background task
```

### Stage Flow

```
Stage 1 — Query Synthesis
  cluster_parser → cluster model
  query_synthesiser → 2-3 queries per subtopic
  Write ci_query_jobs rows (status: queued)
  Update ci_runs status: 'synthesising' → 'discovering'

Stage 2 — Parallel Discovery (asyncio.TaskGroup)
  Per API, per subtopic query — runs concurrently with per-API Semaphore
  Perplexity: POST completions → parse citation URLs
  Semantic Scholar: GET paper/search → citation enrichment (velocity)
  arXiv: GET Atom XML → parse papers
  Each result → ci_raw_results
  Each job → ci_query_jobs (status: done / rate_limited / failed)
  Rate limit (429): exponential backoff 1s → 2s → 4s → mark rate_limited
  Update ci_runs status: 'discovering' → 'deduplicating'

Stage 3 — Dedup & Classification
  URL normalise (strip UTM, trailing slash, force https)
  DOI match across APIs → merge, use SS citation data
  arXiv ID match → merge
  Classify content type by domain
  Assign preliminary source tier (T1-T5)
  Set is_duplicate=true on non-canonical records
  Update ci_runs: 'deduplicating' → 'scoring'

Stage 4 — Scoring
  For each non-duplicate ci_raw_result:
    Topical relevance: keyword density against title + abstract
    Branch: academic (with cites) / academic (preprint) / web
    Normalise signals within content type bucket (percentile rank)
    Apply relevance gate: topical_relevance < 0.25 → excluded
    Compute raw_score, final_score, score_confidence
    Write ci_scored_results

Stage 5 — Complete
  Compute subtopic_relevance_scores (avg per subtopic)
  Update ci_runs: total_discovered, total_deduped, total_scored
  Update ci_runs status: 'scoring' → 'complete'
  Log summary
```

### Rate Limiting (per API)

| API | Free limit | Semaphore | Sleep between requests |
|---|---|---|---|
| Perplexity | No hard limit (cost-based) | 3 concurrent | 0.5s |
| Semantic Scholar | 1 req/sec (free), 10/sec (partner key) | 1 concurrent (no key) | 1.0s (no key), 0.1s (with key) |
| arXiv | ~1 req/3 sec | 1 concurrent | 3.0s |

On 429 or 503: exponential backoff (1s, 2s, 4s). After 3 retries: mark job `rate_limited`, set relevant signal to absent, continue. Pipeline never fails due to a single API failing.

### Scoring Formulas

**Academic — full citation data:**
```
citation_velocity = citations_last_12mo / max(age_months, 1)
raw_score = (citation_velocity_norm × 0.35)
          + (influential_citations_norm × 0.30)
          + (venue_tier_score × 0.20)        # 0=none, 0.5=mid, 1.0=top
          + (topical_relevance × 0.15)
final_score = min(raw_score × tier_multiplier × 100, 100)
score_confidence: 5/5 if all present, fewer if signals missing
```

**Academic — arXiv preprint (no citation data):**
```
raw_score = (topical_relevance × 0.60)
          + (category_tier_score × 0.40)     # cs.AI/cs.LG/cs.CR = 1.0, else 0.5
final_score = min(raw_score × tier_multiplier × 100, 100)
score_confidence: max 3/5
```

**Web content (Perplexity-discovered):**
```
raw_score = (topical_relevance × 0.70)
          + (source_tier_score × 0.30)       # Normalised tier 1-5 → 1.0-0.2
final_score = min(raw_score × tier_multiplier × 100, 100)
score_confidence: max 2/5  ← honest about missing DA/backlinks/social
```

**Relevance gate:** `topical_relevance < 0.25` → `excluded=true`, `excluded_reason='below_relevance_gate'`. Hard rule, not configurable.

**Topical relevance calculation:**
```python
def topical_relevance(text: str, keywords: list[str]) -> float:
    text_lower = text.lower()
    words = text_lower.split()
    word_count = max(len(words), 1)
    keyword_hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    density = keyword_hits / len(keywords)  # fraction of keywords present
    # Cap at 1.0 — repeated keywords don't inflate beyond full coverage
    return min(density, 1.0)
```

Text checked: `title + " " + (abstract_or_snippet or "")`.

---

## 10. Cluster Input Format

User provides JSON via text area or file upload on Screen 1. Format:

```json
{
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
            "indirect prompt injection",
            "prompt injection attacks"
          ]
        },
        {
          "name": "Defence & Mitigation",
          "keywords": [
            "prompt injection defense",
            "input sanitization LLM",
            "dual LLM pattern",
            "CaMeL prompt injection",
            "prompt injection mitigation"
          ]
        },
        {
          "name": "Risks in Production Systems",
          "keywords": [
            "LLM agent security",
            "RAG prompt injection",
            "MCP security vulnerabilities",
            "tool use security",
            "exfiltration attacks LLM"
          ]
        }
      ]
    }
  ]
}
```

**Validation (Pydantic):** Min 1 cluster. Min 1 subtopic per cluster. Min 2 keywords per subtopic. Max 10 subtopics per cluster (to keep API cost bounded). Max 20 keywords per subtopic.

---

## 11. UI Screens

### Screen 1 — Query Configuration (`/`)

Two-column layout using the ai-library dark design system.

**Left column:** Cluster configuration
- JSON text area (syntax-highlighted) with parse-on-paste validation
- Error display if JSON invalid or schema fails
- Or select a previously saved cluster from dropdown
- After parse: auto-render subtopic tick-list (all checked by default)
- Cluster name field (required if saving)
- "Save cluster" button (optional — can run without saving)

**Right column:** Sources + Filters
- **Source tick-list:**
  - ☑ Perplexity (citation URL extraction)
  - ☑ Semantic Scholar (academic papers)
  - ☑ arXiv (preprints)
  - Each shows disabled state with tooltip if key not configured
- **Filters:**
  - Date range: From / To (default: last 12 months)
  - Minimum authority score: 0-100 slider (default: 0)
  - Content types: ☑ Academic ☑ News ☑ Blog ☑ Unknown
- **Run button:** "Start Discovery →" — disabled until cluster is valid and ≥1 source selected

### Screen 2 — Pipeline Progress (`/runs/[id]`)

Polls `GET /runs/{id}` every 3 seconds (same pattern as ai-library pipeline page).

- **Overall status** with animated stage indicator (queued → synthesising → discovering → deduplicating → scoring → complete)
- **Per-source progress table:**

```
Source             Status      Items found
─────────────────────────────────────────
Perplexity         ✓ Done      23 URLs
Semantic Scholar   ◐ Running   41 papers
arXiv              ◦ Queued    —
```

- **Subtopic queries:** "9 queries generated across 3 subtopics"
- **Signal gaps:** ⚠ warnings for rate-limited jobs
- Timing: started at, elapsed
- "View Results →" button appears when status = complete

### Screen 3 — Results Dataset (`/runs/[id]/results`)

**Filter bar:**
- Cluster / Subtopic dropdowns
- Content type: Academic | News | Blog | Unknown
- Source tier: All | T1 | T2 | T3 | T4-5
- Min score slider
- Sort: Score (default) | Citations | Date | Relevance
- [Export CSV] [Export JSON] buttons

**Results table:**
```
# │ Title                        │ Source/Venue  │ Type     │ Tier │ Score │ Conf
──┼──────────────────────────────┼───────────────┼──────────┼──────┼───────┼──────
1 │ Defeating Prompt Injections… │ arXiv/NeurIPS │ Academic │ T1   │ 88    │ ●●●○○
2 │ Simon Willison: Prompt inj…  │ simonwillison │ Blog     │ T3   │ 61    │ ●○○○○
3 │ Design Patterns for Securin… │ arXiv         │ Academic │ T1   │ 79    │ ●●●○○
```

**Row expansion** (click): abstract/snippet, matched keywords, full score breakdown ("Relevance 0.82 × 0.70 weight + Tier T1 × 0.30 weight = raw 0.667 × 1.5 multiplier × 100 = 100"), all contributing APIs.

**Confidence key:** `●` = signal present, `○` = signal absent. Tooltip: "2/5 signals: topical relevance + source tier. Missing: citation velocity, influential citations, backlinks."

**⚠ Row-level warnings:** "Preprint — no citation data. Score confidence capped at 3/5."

**Export:** All columns including component scores, signal flags, matched keywords. Score presented with full provenance, not just the number.

---

## 12. Pre-Mortem Analysis

### Assumptions That Might Not Hold

**"Perplexity will return diverse, authoritative citations"**
Perplexity optimises for answer quality, not domain authority. For niche topics it may consistently return the same 5-6 well-known publications regardless of query variation. Detected via: per-run Perplexity source diversity metric (unique domains ÷ total URLs). Flag if < 5 unique domains in any run.

**"Keyword density is a sufficient relevance signal for soft-case content"**
Analytical insights and principles are often discussed obliquely. A Simon Willison post about prompt injection may not use the phrase "prompt injection" as often as a formal paper — it just demonstrates deep expertise. Keyword density will systematically underrate expert practitioner content. Detected via: manual review of low-scoring results after first 5 runs.

**"3 APIs will return consistent results across runs"**
Perplexity's results for the same query can differ substantially week-to-week. Semantic Scholar citation counts update on varying schedules. Run comparisons over time assume a stability that doesn't exist. Detected via: this is a fundamental property, not a bug. Make no claims about run-to-run comparability.

**"Academic sources (Semantic Scholar, arXiv) are the right track for soft-cases"**
The restructure plan's motivating example is Clay Parker Jones's recommendation — a practitioner thought leader, not an academic. Academic APIs may produce high-authority results that aren't the type of analytical claims we want for Claim Sets. Semantic Scholar and arXiv will consistently surface formal research papers; the practitioner and expert blog content we most want is primarily in Perplexity's output. **This is the most dangerous mismatch.** Score confidence for web content is capped at 2/5 because we don't have DA/backlinks — but web content may be the most valuable content for soft-cases.

**"High authority = high value for Claim Sets"**
Authority scoring was designed to find what practitioners *cite and spread*. For soft-cases, we want what practitioners *argue and reason*. A 50-citation academic paper may be high-authority but analytically thin. A Simon Willison post with extensive reasoning about why prompt injection is hard to solve may be low-authority (T3 tier, no citation data) but high-value for Claim Sets. The authority score does not distinguish these.

**"The cluster hierarchy maps cleanly to how experts discuss topics"**
Subtopics like "Defence & Mitigation" impose our vocabulary on a topic where experts may use entirely different framing. Relevance scoring will miss highly relevant content that uses different terminology.

### Most Likely First Failure in Production

**Rate limit cascade on Semantic Scholar free tier.**

Without an API key, Semantic Scholar allows 1 request/second. A cluster with 3 subtopics × 3 queries per subtopic = 9 SS requests + citation enrichment calls per discovered paper. A modest run surfacing 30 SS papers generates 30+ citation enrichment calls. At 1 req/sec, that's 30+ seconds of sequential Semantic Scholar calls — blocking the scoring stage.

**What breaks:** Runs appear to hang in `discovering` status. The 30-minute stale threshold eventually marks them failed. Users re-trigger runs. The cycle repeats.

**Mitigation already in plan:** `asyncio.Semaphore(1)` + 1s sleep for free tier. Citation enrichment calls are batched with the same limiter. If Semantic Scholar partner key is set, increase to `Semaphore(10)` + 0.1s sleep.

**Second most likely:** Perplexity citation URL parsing breaks on a response format change. Perplexity doesn't document its citation format and changes it without notice. The parser returns empty URL list; run completes with `total_discovered: 0` from Perplexity but SS and arXiv data. This is not catastrophic — graceful degradation — but it's invisible unless monitored.

### Six-Month Failure Post-Mortem

**The authority scores were trusted without reviewing the content.**

After the first few runs returned impressive-looking scores, people stopped clicking through to verify that high-scoring items were actually useful for Claim Set purposes. The academic papers scoring T1/88 were rigorously cited but analytically thin — they measured things rather than argued positions. The Simon Willison-type practitioner posts scoring T3/42 were exactly the Claim Set material we needed, but were buried on page 3 of results sorted by score.

The system was optimised for academic citation authority. Soft-cases need practitioner analytical authority. These are different things and the scoring model didn't distinguish them.

**The cluster keywords became stale within weeks.**

"Prompt injection" as a search term was fine in early 2026. By mid-year, the field had fragmented into "agentic AI security", "tool poisoning", "MCP attack surface", and "autonomous agent exploitation". Our cluster keywords didn't capture any of these. Runs returned the same evergreen papers run after run. Users initially read this as stability; after 2 months it became clear the discovery was broken.

**Perplexity became a single point of failure for web content.**

Web content — the practitioner posts, blog series, expert Substacks — was only discovered through Perplexity. When Perplexity changed their citation format in late April, the parser returned empty for every Perplexity job. Web content discovery went to zero. The gap wasn't detected for 11 days because the academic tracks (SS + arXiv) were still returning results and the UI didn't clearly distinguish discovery source breakdown.

**The score confidence cap for web content was confusing, not clarifying.**

"Score confidence 2/5" on web content looked like a problem with the result, not a property of the scoring model. Users began filtering out results with confidence < 4/5, which eliminated all web content. The most valuable results for Claim Sets were systematically excluded.

---

## 13. Risk Matrix

Scoring: **Likelihood × Impact × Detectability** where Detectability 3 = silent failure (hardest to catch). RPN = L × I × D.

Priority bands: 🔴 High (RPN 18-27), 🟡 Medium (RPN 9-17), 🟢 Low (RPN 1-8).

| # | Risk | L (1-3) | I (1-3) | D (1-3) | RPN | Priority | Mitigation |
|---|---|---|---|---|---|---|---|
| R1 | **Authority ≠ value for soft-cases.** High-authority academic papers score well; practitioner analytical content scores poorly. Users sort by score and miss the best Claim Set material. | 3 | 3 | 3 | **27** | 🔴 | Add a "Content type" filter with `blog/news` separate from `academic`. Show web content in its own results section. Add tooltip: "For Claim Sets, practitioner posts may outweigh academic papers despite lower scores." After 5 runs, review whether sorting by score correlates with Claim Set value. |
| R2 | **Cluster keyword staleness.** Field terminology evolves; keywords don't. Runs keep returning the same evergreen content. | 3 | 3 | 3 | **27** | 🔴 | After each run, compute avg topical relevance per subtopic. Flag any subtopic with avg < 0.30 as "⚠ Low relevance — review keywords." Show this in the run summary on Screen 2. Schedule keyword review after every 10 runs. |
| R3 | **Perplexity citation parser breaks on format change.** Web content discovery goes to zero silently. | 3 | 3 | 2 | **18** | 🔴 | Per-run metric: `perplexity_urls_found`. If 0 for any run where Perplexity was enabled, log `perplexity_parser_zero` at ERROR level. Show ⚠ in run summary: "Perplexity returned 0 URLs — parser may need updating." Weekly manual check for first month. |
| R4 | **Semantic Scholar free-tier rate limiting hangs runs.** | 3 | 2 | 2 | **12** | 🟡 | `asyncio.Semaphore(1)` + 1s sleep. Citation enrichment uses same semaphore. 30-min stale threshold marks hung runs as failed with helpful message: "Semantic Scholar rate limited — consider adding an API key." |
| R5 | **Score confidence 2/5 on web content causes users to filter it out.** Best Claim Set material excluded. | 2 | 3 | 2 | **12** | 🟡 | Don't default-filter by confidence. Confidence indicator visible on all rows. Tooltip explains: "Web content has fewer scoreable signals — lower confidence doesn't mean lower quality for Claim Sets." |
| R6 | **arXiv pagination unreliable beyond 1000 results.** Known arXiv issue. | 1 | 2 | 2 | **4** | 🟢 | Design queries to stay under 50 results per query. 20 max results per SS/arXiv query is already planned. |
| R7 | **Perplexity source diversity too narrow.** Same 5-6 publications cited in every run regardless of subtopic variation. | 2 | 2 | 3 | **12** | 🟡 | Per-run metric: unique Perplexity domains ÷ total Perplexity URLs. If < 30% unique domains, flag: "⚠ Perplexity source diversity low — consider query variation." |
| R8 | **No social velocity signal means high-impact practitioner posts underscored.** Simon Willison-type content with massive Twitter/community engagement has no signal in MVP. | 3 | 2 | 1 | **6** | 🟢 | Acknowledged in plan. Phase 3 adds Apify/X social velocity. Document limitation clearly in UI: "Social velocity not yet scored. Phase 2 adds this signal." |
| R9 | **Dedup misses overlapping Perplexity + SS results.** Same paper cited by URL (Perplexity) and DOI (SS) without link. | 2 | 1 | 2 | **4** | 🟢 | Dedup also does title similarity check (normalised Levenshtein) as fallback when URL/DOI/arxivID don't match directly. |
| R10 | **`topical_relevance < 0.25` gate excludes valid results.** Threshold may be too aggressive for specialist terminology. | 2 | 2 | 2 | **8** | 🟢 | Excluded results still written to `ci_scored_results` with `excluded=true`. Visible in UI with toggle "Show excluded." Count of excluded items shown in run summary. |

### Top 3 Silent Failures (Detectability = 3, highest risk)

1. **R1: Authority ≠ value** — users get clean results but miss the point
2. **R2: Cluster staleness** — system appears to work; quality silently declines
3. **R3: Perplexity parser breaks** — web content goes to zero; academic results mask the gap

All three require proactive monitoring signals (per-run metrics, alerts, scheduled reviews) — they will not surface through normal use.

---

## 14. Test Plan

All tests are in `backend/app/tests/citation_intel/`. Tests run with:

```bash
cd soft-cases/backend
pytest app/tests/citation_intel/ -v
```

No test ever makes a real API call. All external responses are captured as fixture files in `app/tests/citation_intel/fixtures/`.

### Unit Tests

#### `test_cluster_parser.py`

```python
test_parses_valid_cluster_json()
    # Input: valid cluster with 1 pillar, 2 clusters, 3 subtopics each
    # Assert: ClusterModel with correct counts, all keywords accessible

test_rejects_cluster_missing_subtopics()
    # Input: cluster with empty subtopics list
    # Assert: ValidationError raised

test_rejects_subtopic_with_one_keyword()
    # Input: subtopic with only 1 keyword
    # Assert: ValidationError raised (min 2 keywords)

test_rejects_cluster_exceeding_subtopic_limit()
    # Input: cluster with 11 subtopics
    # Assert: ValidationError raised (max 10)

test_accepts_cluster_at_exact_subtopic_limit()
    # Input: cluster with 10 subtopics
    # Assert: parsed successfully

test_pillar_name_required()
    # Input: JSON with pillar = ""
    # Assert: ValidationError raised
```

#### `test_query_synthesiser.py`

```python
test_generates_2_to_3_queries_per_subtopic()
    # Input: subtopic with 5 keywords
    # Assert: len(queries) in [2, 3]

test_query_contains_discriminating_keywords()
    # Input: subtopic "Attack Vectors", keywords ["prompt injection", "jailbreaking"]
    # Assert: at least 2 of the keywords appear across the generated queries

test_query_does_not_exceed_500_chars()
    # Input: subtopic with 20 long keywords
    # Assert: all generated queries < 500 characters

test_produces_distinct_queries()
    # Input: subtopic with 5 keywords
    # Assert: no two generated queries are identical

test_handles_single_keyword_subtopic_gracefully()
    # Input: subtopic with 2 keywords (minimum)
    # Assert: returns at least 1 query, no exception
```

#### `test_dedup.py`

```python
test_identical_urls_after_utm_strip_are_duplicates()
    # Input: ["https://example.com/article?utm_source=twitter", "https://example.com/article"]
    # Assert: second marked is_duplicate=True; canonical=first

test_doi_match_across_sources_merges_records()
    # Input: SS result (doi="10.1234/paper") + arXiv result (doi="10.1234/paper")
    # Assert: one canonical record; is_duplicate=True on the other; discovered_by includes both APIs

test_arxiv_id_match_merges_records()
    # Input: SS result (arxiv_id="2301.12345") + arXiv result (arxiv_id="2301.12345")
    # Assert: merged; SS citation data used on canonical

test_different_urls_same_domain_are_not_duplicates()
    # Input: ["https://arxiv.org/abs/2301.11111", "https://arxiv.org/abs/2301.22222"]
    # Assert: neither marked duplicate

test_url_normalise_strips_trailing_slash()
    # Input: "https://example.com/path/" vs "https://example.com/path"
    # Assert: same dedup_key

test_url_normalise_forces_https()
    # Input: "http://example.com/path" vs "https://example.com/path"
    # Assert: same dedup_key

test_null_url_null_doi_null_arxiv_not_merged()
    # Input: two results with all null identifiers
    # Assert: neither marked duplicate (can't confirm identity)
```

#### `test_classifier.py`

```python
test_edu_domain_is_tier_1()
    # Input: url="https://ai.stanford.edu/paper"
    # Assert: source_tier=1, tier_multiplier=1.5

test_gov_domain_is_tier_1()
    # Input: url="https://nist.gov/ai-framework"
    # Assert: source_tier=1

test_arxiv_cs_ai_is_tier_1()
    # Input: arxiv categories=["cs.AI"]
    # Assert: category_tier=1

test_arxiv_unknown_category_is_tier_2()
    # Input: arxiv categories=["econ.GN"]
    # Assert: category_tier=2

test_simonwillison_is_tier_3()
    # Input: url="https://simonwillison.net/2025/anything"
    # Assert: source_tier=3

test_unknown_domain_is_tier_4_or_5()
    # Input: url="https://randomnewblog.io/post"
    # Assert: source_tier in [4, 5]

test_semantic_scholar_result_classified_as_academic()
    # Input: raw_result with source_api="semantic_scholar"
    # Assert: content_type="academic"

test_perplexity_url_classified_by_domain()
    # Input: raw_result with source_api="perplexity", url="https://hbr.org/..."
    # Assert: content_type="news" or "blog"
```

#### `test_scoring_academic.py`

```python
test_full_citation_formula_weights_sum_to_1()
    # Assert: 0.35 + 0.30 + 0.20 + 0.15 == 1.0

test_citation_velocity_calculation()
    # Input: 120 citations in last 12 months, paper age 24 months
    # Assert: citation_velocity = 120/24 = 5.0

test_citation_velocity_zero_months_does_not_divide_by_zero()
    # Input: paper published today (age_months = 0)
    # Assert: citation_velocity = 0 (not error)

test_t1_multiplier_applied()
    # Input: source_tier=1, raw_score=0.6
    # Assert: final_score = 0.6 × 1.5 × 100 = 90

test_final_score_capped_at_100()
    # Input: raw_score=0.9, tier_multiplier=1.5
    # Assert: final_score = 100 (not 135)

test_preprint_formula_different_from_full()
    # Input: is_preprint=True, no citation data, topical_relevance=0.8, category_tier=1
    # Assert: raw_score = 0.8×0.60 + 1.0×0.40 = 0.88
    # Assert: score_confidence <= 3

test_missing_citation_data_does_not_throw()
    # Input: citation_count=None, influential_citations=None
    # Assert: returns valid score with reduced score_confidence

test_preprint_score_confidence_max_3()
    # Input: arXiv preprint with all fields present except citations
    # Assert: score_confidence == 3
```

#### `test_scoring_web.py`

```python
test_web_formula_weights_sum_to_1()
    # Assert: 0.70 + 0.30 == 1.0

test_web_score_confidence_max_2()
    # Input: Perplexity result with title + abstract
    # Assert: score_confidence <= 2

test_t3_multiplier_applied_to_web()
    # Input: source_tier=3, raw_score=0.5
    # Assert: final_score = 0.5 × 1.1 × 100 = 55.0
```

#### `test_normalise.py`

```python
test_percentile_normalisation_produces_0_to_1_range()
    # Input: [10, 20, 30, 40, 50]
    # Assert: all normalised values in [0.0, 1.0]

test_percentile_normalisation_preserves_order()
    # Input: [10, 20, 30]
    # Assert: norm(10) < norm(20) < norm(30)

test_single_value_normalises_to_1()
    # Input: [42] (only one item in bucket)
    # Assert: normalised = 1.0 (not error, not 0)

test_equal_values_normalise_identically()
    # Input: [50, 50, 50]
    # Assert: all normalised values equal
```

#### `test_topical_relevance.py`

```python
test_all_keywords_present_gives_1_0()
    # Input: text="prompt injection attack jailbreaking adversarial", keywords=["prompt injection", "jailbreaking", "adversarial"]
    # Assert: topical_relevance = 1.0

test_no_keywords_present_gives_0_0()
    # Input: text="unrelated content about cats", keywords=["prompt injection", "jailbreaking"]
    # Assert: topical_relevance = 0.0

test_partial_keywords_gives_fractional_score()
    # Input: text="prompt injection attack", keywords=["prompt injection", "jailbreaking", "adversarial"]
    # Assert: topical_relevance ≈ 0.33

test_relevance_gate_excludes_below_0_25()
    # Input: topical_relevance=0.24
    # Assert: excluded=True, excluded_reason="below_relevance_gate"

test_relevance_gate_passes_at_0_25()
    # Input: topical_relevance=0.25
    # Assert: excluded=False

test_case_insensitive_matching()
    # Input: text="Prompt Injection ATTACK", keywords=["prompt injection"]
    # Assert: topical_relevance = 1.0
```

### Integration Tests (Fixture-Based — No Real API Calls)

Fixtures are captured real API response shapes stored as JSON in `tests/citation_intel/fixtures/`.

#### `test_service_perplexity.py`

```python
test_parses_citation_urls_from_prose_response(perplexity_fixture)
    # Fixture: real Perplexity response with 4 inline citations
    # Assert: returns 4 URLs, all valid https:// strings

test_handles_footnote_style_citations(perplexity_fixture_footnotes)
    # Fixture: response using [1], [2] footnote style
    # Assert: URLs correctly extracted

test_deduplicates_repeated_citations(perplexity_fixture_repeated)
    # Fixture: same URL cited 3 times in one response
    # Assert: returns 1 URL (not 3)

test_returns_empty_list_on_no_citations(perplexity_fixture_no_citations)
    # Fixture: valid Perplexity response with no source citations
    # Assert: returns [], no exception

test_handles_malformed_json_gracefully(perplexity_fixture_malformed)
    # Fixture: Perplexity returns invalid JSON
    # Assert: raises ParseError or returns [], logs error, does not crash pipeline

test_429_response_signals_rate_limit(mock_perplexity_429)
    # Mock: httpx returns 429
    # Assert: raises RateLimitError (for retry logic to catch)
```

#### `test_service_semantic_scholar.py`

```python
test_parses_paper_search_response(ss_search_fixture)
    # Fixture: real SS /paper/search response with 5 papers
    # Assert: returns 5 SemanticScholarPaper objects with expected fields

test_extracts_citation_count(ss_search_fixture)
    # Assert: citation_count populated for papers where SS provides it

test_extracts_influential_citation_count(ss_search_fixture)
    # Assert: influentialCitationCount mapped to influential_citations

test_handles_empty_results_array(ss_empty_fixture)
    # Fixture: SS returns { "data": [] }
    # Assert: returns [], no exception

test_handles_missing_optional_fields(ss_partial_fixture)
    # Fixture: paper with null venue, null year
    # Assert: returns result with None values, no exception

test_429_signals_rate_limit(mock_ss_429)
    # Assert: raises RateLimitError

test_citation_velocity_enrichment(ss_citations_fixture)
    # Fixture: /paper/{id}/citations response with timestamps
    # Assert: citation_velocity correctly calculated from last 12 months of citations
```

#### `test_service_arxiv.py`

```python
test_parses_atom_feed(arxiv_atom_fixture)
    # Fixture: real arXiv Atom XML with 5 papers
    # Assert: returns 5 ArxivPaper objects with correct fields

test_extracts_arxiv_id(arxiv_atom_fixture)
    # Assert: arxiv_id extracted correctly from entry id URL

test_extracts_doi_when_present(arxiv_atom_fixture_with_doi)
    # Fixture: arXiv paper with journal_ref and DOI
    # Assert: doi field populated

test_marks_no_doi_as_preprint(arxiv_atom_fixture)
    # Assert: papers without doi have is_preprint=True

test_extracts_categories(arxiv_atom_fixture)
    # Assert: categories list populated e.g. ["cs.AI", "cs.LG"]

test_filters_results_outside_date_range(arxiv_atom_fixture_old)
    # Fixture: papers with published dates spanning 3 years
    # Input: filter last_12_months=True
    # Assert: only papers within last 12 months returned

test_handles_empty_feed(arxiv_empty_fixture)
    # Fixture: valid Atom feed with 0 entries
    # Assert: returns [], no exception

test_rate_limit_enforced_between_requests(mock_arxiv)
    # Mock: tracks request timestamps
    # Assert: minimum 3 seconds between consecutive requests
```

### Pipeline Integration Tests (Mocked Services, Full Flow)

#### `test_pipeline_integration.py`

```python
test_full_pipeline_runs_stage_1_through_5(mock_all_services, test_db)
    # Mock: all 3 API services return fixture data
    # Input: simple 1-cluster, 2-subtopic config
    # Assert: ci_runs status = 'complete'
    # Assert: ci_query_jobs has 1 row per subtopic per API (6 jobs)
    # Assert: ci_raw_results has > 0 rows
    # Assert: ci_scored_results has > 0 rows

test_dedup_reduces_overlapping_results(mock_services_with_overlap, test_db)
    # Mock: SS and arXiv return same paper (same DOI)
    # Assert: only 1 ci_scored_results row for that paper
    # Assert: discovered_by contains both "semantic_scholar" and "arxiv"

test_relevance_gate_excludes_irrelevant_results(mock_services_irrelevant, test_db)
    # Mock: all returned results have 0 keyword matches
    # Assert: all ci_scored_results rows have excluded=True
    # Assert: ci_runs.total_scored = 0

test_rate_limited_api_does_not_fail_pipeline(mock_ss_always_429, test_db)
    # Mock: Semantic Scholar returns 429 on every call
    # Assert: ci_runs status = 'complete' (not 'failed')
    # Assert: ci_query_jobs SS rows have status = 'rate_limited'
    # Assert: Perplexity and arXiv results still scored

test_all_apis_failing_marks_run_complete_with_zero_results(mock_all_429, test_db)
    # Mock: all 3 APIs return 429 after retries
    # Assert: ci_runs status = 'complete' (not 'failed')
    # Assert: ci_runs.total_scored = 0
    # Assert: all ci_query_jobs rows = 'rate_limited'

test_subtopic_relevance_scores_computed_per_run(mock_all_services, test_db)
    # Assert: ci_runs.subtopic_relevance_scores is a dict with one key per subtopic
    # Assert: all values between 0.0 and 1.0

test_csv_export_includes_all_scored_results(mock_all_services, test_db)
    # Assert: CSV row count = ci_runs.total_scored
    # Assert: CSV has required headers: title, url, final_score, score_confidence, content_type, ...
    # Assert: excluded=True rows NOT in CSV (only scored results)

test_json_export_includes_component_scores(mock_all_services, test_db)
    # Assert: each JSON item has raw_score, final_score, topical_relevance, score_confidence
    # Assert: citation_velocity present and non-null for academic items with citation data

test_stale_run_detection(test_db)
    # Set up: ci_runs row with status='discovering', updated_at=2 hours ago
    # Trigger: startup lifespan stale check
    # Assert: run status set to 'failed', error_message contains "Server restarted"
```

### Running Tests

```bash
# Install test dependencies
cd soft-cases/backend
pip install -r requirements.txt

# Run all citation intel tests
pytest app/tests/citation_intel/ -v

# Run with coverage
pytest app/tests/citation_intel/ -v --cov=app/citation_intel --cov-report=term-missing

# Run a specific file
pytest app/tests/citation_intel/test_dedup.py -v

# Run a specific test
pytest app/tests/citation_intel/test_scoring_academic.py::test_final_score_capped_at_100 -v
```

**Target before starting Phase E (frontend):** All unit tests and integration tests passing. Pipeline integration tests passing with mocked services.

**Target before first live run:** Above + at least `test_pipeline_integration.py::test_full_pipeline_runs_stage_1_through_5` passing with real fixture data captured from a dry run.

---

## 15. Build Sequence — Locked

### Phase A — Foundation (1 session)

| Step | Task | Tests written first |
|---|---|---|
| A1 | Scaffold `soft-cases/` folder: `backend/`, `frontend/`, `docs/`, `railway.toml`, `.env.example` | — |
| A2 | `requirements.txt`, `pyproject.toml`, `config.py`, `database.py`, `main.py` (same patterns as ai-library) | — |
| A3 | Alembic init + migration `001_citation_intel_tables.py` (all 5 `ci_*` tables) | — |
| A4 | `cluster_parser.py` with Pydantic models | `test_cluster_parser.py` (all 6 tests) |
| A5 | `query_synthesiser.py` | `test_query_synthesiser.py` (all 5 tests) |
| A6 | `router.py` with `POST /runs` (creates run, returns id), `GET /runs/{id}` (status), `GET /health` | — |

**Gate:** All Phase A unit tests pass. `GET /health` returns 200.

### Phase B — Discovery Services (1-2 sessions)

| Step | Task | Tests written first |
|---|---|---|
| B1 | `services/semantic_scholar.py` + rate limiter | `test_service_semantic_scholar.py` (all 8 tests) |
| B2 | `services/arxiv.py` (Atom XML parser, rate limiter) | `test_service_arxiv.py` (all 8 tests) |
| B3 | `services/perplexity.py` (citation URL extraction) | `test_service_perplexity.py` (all 6 tests) |
| B4 | `dedup.py` | `test_dedup.py` (all 7 tests) |
| B5 | `pipeline.py` — Stages 1-3 (synthesis → discovery → dedup) | `test_pipeline_integration.py::test_full_pipeline_runs_stage_1_through_5` |
| B6 | `GET /runs/{id}/jobs` endpoint — per-source job status | — |

**Gate:** All Phase B integration tests pass with fixture data. Capture real API fixtures by running once with real keys (single subtopic, 5 results max per API).

### Phase C — Scoring (1 session)

| Step | Task | Tests written first |
|---|---|---|
| C1 | `classifier.py` + `data/source_tiers.json` | `test_classifier.py` (all 8 tests) |
| C2 | `test_topical_relevance.py` (6 tests) → `topical_relevance()` function | `test_topical_relevance.py` |
| C3 | `scoring/normalise.py` | `test_normalise.py` (all 4 tests) |
| C4 | `scoring/academic.py` | `test_scoring_academic.py` (all 8 tests) |
| C5 | `scoring/web.py` | `test_scoring_web.py` (all 3 tests) |
| C6 | `pipeline.py` — Stages 4-5 (scoring → complete) | Remaining `test_pipeline_integration.py` tests |
| C7 | `GET /runs/{id}/results` endpoint (paginated, filterable) | — |

**Gate:** All scoring unit tests pass. Full pipeline integration test passes with mocked services.

### Phase D — Export + API Polish (0.5 session)

| Step | Task |
|---|---|
| D1 | `GET /runs/{id}/export/csv` — all columns including component scores |
| D2 | `GET /runs/{id}/export/json` |
| D3 | `GET /runs`, `POST /clusters`, `GET /clusters`, `GET /clusters/{id}` |
| D4 | CSV/JSON export integration tests |

**Gate:** `test_csv_export_includes_all_scored_results` and `test_json_export_includes_component_scores` passing.

### Phase E — Frontend (2 sessions)

| Step | Task |
|---|---|
| E1 | Next.js 15 scaffold, Tailwind config, design system tokens (reuse ai-library dark theme palette) |
| E2 | Shared UI components: `Button`, `Card`, `Chip`, `Kicker`, `Input` (copy from ai-library, adapt) |
| E3 | Screen 1 — Query configuration page (`/`): JSON input, subtopic tick-list, source/filter controls, run trigger |
| E4 | Screen 2 — Pipeline progress page (`/runs/[id]`): polling, per-source status table, stage progress |
| E5 | Screen 3 — Results page (`/runs/[id]/results`): filterable/sortable table, row expansion, confidence indicators |
| E6 | Export buttons (CSV + JSON download) |
| E7 | Navigation between screens, error states, empty states |

**Gate:** All three screens functional against locally running backend. Manual walkthrough complete.

### Phase F — First Live Run + Validation (1 session)

| Step | Task |
|---|---|
| F1 | Run "Prompt Injection" cluster against all 3 APIs with real keys |
| F2 | Review results: Does Simon Willison's series appear? Do academic papers appear? Are scores plausible? |
| F3 | Check Perplexity source diversity (>5 unique domains?) |
| F4 | Check subtopic relevance scores (any < 0.30 flagged?) |
| F5 | Export CSV — verify all columns, all scores present |
| F6 | Document findings in `docs/first-run-report.md` (what worked, what didn't) |
| F7 | Update `data/source_tiers.json` based on domains that appeared |

**Gate:** At least 20 scored results. Perplexity returns >5 unique domains. Simon Willison series appears (validates practitioner content discovery). Academic papers from Semantic Scholar/arXiv appear.

---

## 16. Stale Run Recovery

Matches ai-library pattern exactly. In `main.py` lifespan:

```python
# On startup: mark runs stuck in non-terminal states for > 30 min as failed
threshold = datetime.now(timezone.utc) - timedelta(minutes=30)
await session.execute(
    update(CIRun)
    .where(
        CIRun.status.notin_(["complete", "failed"]),
        CIRun.updated_at < threshold,
    )
    .values(
        status="failed",
        error_message="Server restarted during pipeline execution",
    )
)
```

---

## 17. Integration Path to Case Library Restructure

When Phase 1 of the restructure plan begins:

```
soft-cases/backend/app/citation_intel/   →  ai-library/backend/app/citation_intel/
soft-cases/frontend/app/                 →  ai-library/frontend/app/research/
soft-cases DB (ci_* tables)              →  ai-library DB (same tables, same schemas)
soft-cases/ folder                       →  retired
```

The `ci_scored_results` table is designed so high-scoring results feed directly into the VEP's Agent 2 as URLs to extract. The integration adds:
- A "Send to VEP" action on results (triggers VEP extraction against the URL)
- Triage logic: if VEP finds org-anchored claims → Case; if concept-anchored → Claim Set
- `parent_type` + `parent_id` on claims table linking to either `cases` or `claim_sets`

This MVP is **Phase 0.5** — it delivers standalone value (authoritative source discovery) and produces the exact data structure that Phase 1 needs.

---

## 18. Railway Deployment (When Ready)

| Concern | Setting |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Pre-deploy | `alembic upgrade head` |
| Health check | `GET /health → 200 { "status": "ok" }` |
| PostgreSQL | Railway PostgreSQL plugin |
| ENV vars | Set in Railway dashboard. Never committed. Mirror in `.env.local`. |

---

*Plan status: Build-ready. All decisions locked. Proceed to Phase A.*
