# Soft-Cases -> AI Library Integration Analysis

**Date:** 10 Mar 2026  
**Scope:** Step 4, Step 5, and Step 6 of the integration plan  
**Repos involved:** `soft-cases`, `ai-library`

---

## 1) Objective

Integrate Citation Intelligence from `soft-cases` into `ai-library` so discovery, scoring, and VEP handoff run in one product surface (`/research`) with one backend domain and one database.

The integration must preserve:
- existing ACL behavior
- CI provenance (`raw_result_id`, `discovered_by`, source metadata)
- migration safety and rollback path

---

## 2) Current State Snapshot

### Soft-cases (today)
- Full CI pipeline exists and is tested
- Tables: `ci_clusters`, `ci_runs`, `ci_query_jobs`, `ci_raw_results`, `ci_scored_results`
- Endpoints mounted at `/api/v1/*`
- Frontend pages: `/`, `/runs/[id]`, `/runs/[id]/results`

### AI library (today)
- Existing case library + extraction stack
- Separate schema and Alembic chain
- No integrated `/research` CI routes yet
- `claim_sets` existence in live DB not yet confirmed (Step 4 gate)

---

## 3) Decision Gates (Must Pass Before Merge)

## Gate A — Live ACL DB audit
Run against Railway production ACL database:
1. List tables
2. Inspect `claims` structure
3. Determine if `claim_sets` exists
4. Verify source/evidence model shape

If `claim_sets` does not exist, add it first in ACL migrations before CI->VEP linking work.

## Gate B — Alembic compatibility
- Map ACL current head revision
- Renumber/port CI migrations so ACL graph stays linear and deploy-safe
- Test `alembic upgrade head` from clean DB and from existing ACL snapshot

## Gate C — API and UI route compatibility
- Confirm ACL backend can host CI router under `/api/v1/research/*` (recommended)
- Confirm ACL frontend nav and layout can host `/research` routes without regressions

---

## 4) Integration Work Breakdown (Step 5)

## 5a — Database: `claim_sets` and claim parent model

### Required model decisions
- `claim_sets` table columns:
  - `id` (uuid)
  - `pillar`
  - `cluster_name`
  - `subtopic`
  - `created_at`
- `claims.parent_type`: `"case"` or `"claim_set"`
- `claims.parent_id`: FK to either parent object (enforced in app logic, with migration-safe constraints)

### Risk points
- Existing `claims` queries that assume only case parentage
- Existing serializers/admin screens that do not expect `parent_type`

### Mitigation
- Add compatibility views/helpers for old code paths
- Add query-level guards before switching default behavior

---

## 5b — Backend merge: `citation_intel` into ACL

### Files to port
- `soft-cases/backend/app/citation_intel/*`
- `soft-cases` CI migrations (renumbered for ACL chain)
- New filter gate module (`pipeline/filter.py`)
- Router registration in ACL `main.py`

### Contract recommendations
- Keep CI router internally namespaced (`/api/v1/research/...`) to avoid route collisions
- Keep table prefix `ci_` in ACL DB for provenance clarity

### Risk points
- Migration ID conflicts
- Config mismatch (`auth_secret`, API keys, CORS)
- Background task behavior under ACL runtime profile

### Mitigation
- Integration branch with isolated migration test matrix:
  - fresh DB
  - current prod-like snapshot
  - rollback simulation

---

## 5c — Frontend merge: `/research` in ACL

### Route mapping
- `soft-cases/frontend/app/page.tsx` -> `ai-library/frontend/app/research/page.tsx`
- `.../runs/[id]/page.tsx` -> `.../research/runs/[id]/page.tsx`
- `.../runs/[id]/results/page.tsx` -> `.../research/runs/[id]/results/page.tsx`

### Layout changes
- Add `Research` nav link in ACL layout/nav component
- Update API base URLs so research calls target ACL backend domain

### Risk points
- Path assumptions hardcoded in links/navigation
- Shared component token mismatches

### Mitigation
- Add route-level smoke tests for `/research` pages
- Run focused visual regression checks on ACL nav/header

---

## 5d — Wire "Send to VEP"

### Functional target
On results page, high-scoring rows (`final_score >= 70`) expose action:
- "Send to VEP"
- payload includes source URL and CI context

### Triage rule
- org-anchored extraction -> create/attach to Case
- concept-anchored extraction -> create/attach to Claim Set

### Risk points
- ambiguity in extraction classification
- duplicate ingestion on repeated clicks

### Mitigation
- idempotency key per `(run_id, raw_result_id)` handoff
- explicit triage confidence and manual override path in admin mode

---

## 5) Testing Requirements for Integration Branch

## Mandatory before deploy
1. CI pipeline regression suite passes in ACL backend
2. ACL existing tests pass unchanged
3. Migration upgrade path tested from current ACL production baseline
4. `/research` UI flow tested end-to-end
5. VEP handoff idempotency and parent routing tested

## Smoke tests after deploy
1. Run Prompt Injection cluster
2. Load results page without serialization errors
3. Validate pagination with excluded rows hidden
4. Trigger CSV export
5. Execute one "Send to VEP" for each triage path (case + claim_set)

---

## 6) Rollback Strategy

If integration deployment fails:
1. Disable `/research` nav link (feature flag)
2. Keep CI tables in DB (do not drop during incident)
3. Revert router registration and frontend route exposure
4. Preserve soft-cases standalone service as fallback until ACL integration is stable

Step 6 (retire standalone soft-cases services) must only happen after:
- 2+ successful end-to-end runs in ACL production
- no data integrity issues in `claims` parent routing

---

## 7) Recommended Execution Order

1. **Step 4 audit**: schema truth from live ACL DB
2. **DB prep**: `claim_sets` + `claims` parent model migration(s)
3. **Backend merge**: CI modules + router + tests
4. **Frontend merge**: `/research` routes + nav link
5. **VEP wiring**: send action + triage + idempotency
6. **Prod smoke run**
7. **Retire standalone services**

---

## 8) Open Questions to Resolve at Step 4

1. Does ACL already have a concept grouping table equivalent to `claim_sets`?
2. Are there ACL constraints that assume `claim.parent_id` always points to `cases.id`?
3. Is ACL using strict enum constraints that need extension for `parent_type`?
4. Which ACL endpoint is canonical for VEP ingestion in production?
5. Do we need a user-visible audit trail for "sent from research run X"?

These answers determine the final migration design and API wiring details for Step 5.
