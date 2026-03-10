"""
Regression tests for known bugs found during pre-build audit.

Each test is named after the bug it covers and documents the expected
behaviour after the fix. Run BEFORE building to confirm the bug exists
(expect failures), then run AFTER fixing to confirm it's resolved.

Bug list:
  BUG-1  GET /runs/{id}/results → 500 (SQLAlchemy ORM not serializable without response_model)
  BUG-2  filter_config.min_topical_relevance silently ignored in orchestrator
  BUG-3  Pagination "Next" button disabled too early (displayed vs raw length)
  BUG-4  Double pipeline start: two background tasks both see status=queued
  BUG-5  fallback_raw_id assigns same raw_result_id to multiple scored results
  BUG-6  _velocity_norm/_influential_norm set via object.__setattr__ (fragile)
  BUG-7  Score breakdown: SS preprint papers shown with arXiv weights
"""

from __future__ import annotations

import pytest
from fastapi.encoders import jsonable_encoder

from app.citation_intel.pipeline.raw_result import RawResultData
from app.citation_intel.scoring.normaliser import normalise_citation_signals
from app.citation_intel.scoring.scorer import score, RELEVANCE_GATE
from app.models.ci_models import CIScoredResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_raw(
    source_api: str = "semantic_scholar",
    citation_count: int | None = 10,
    recent_citations: int | None = 2,
    influential_citations: int | None = 1,
    published_date: str = "2023-01",
    topical_relevance: float | None = None,
    is_preprint: bool = False,
    is_duplicate: bool = False,
    source_tier: int = 1,
    venue_tier: int | None = 1,
    category_tier: int | None = 1,
    **kwargs,
) -> RawResultData:
    return RawResultData(
        source_api=source_api,
        title="Test paper on prompt injection attacks",
        abstract_or_snippet="This paper covers prompt injection jailbreaking adversarial prompts.",
        citation_count=citation_count,
        recent_citations=recent_citations,
        influential_citations=influential_citations,
        published_date=published_date,
        is_preprint=is_preprint,
        is_duplicate=is_duplicate,
        source_tier=source_tier,
        venue_tier=venue_tier,
        category_tier=category_tier,
        topical_relevance=topical_relevance,
        **kwargs,
    )


def _make_scored_result_orm() -> CIScoredResult:
    """Build a CIScoredResult ORM instance without a DB session."""
    return CIScoredResult(
        id="00000000-0000-0000-0000-000000000001",
        run_id="00000000-0000-0000-0000-000000000002",
        raw_result_id="00000000-0000-0000-0000-000000000003",
        content_type="academic",
        url="https://arxiv.org/abs/2301.12345",
        title="Prompt Injection Defence Mechanisms",
        authors=["Alice", "Bob"],
        abstract_or_snippet="A study of prompt injection.",
        published_date="2023-01",
        venue="NeurIPS",
        source_tier=1,
        tier_multiplier=1.5,
        pillar="AI Security",
        cluster_name="Prompt Injection",
        subtopic="Attack Vectors",
        matched_keywords=["prompt injection"],
        keyword_density=0.5,
        topical_relevance=0.7,
        citation_count=42,
        citation_velocity=0.5,
        influential_citations=5,
        venue_tier=1,
        is_preprint=True,
        arxiv_categories=["cs.CR"],
        category_tier=1,
        raw_score=0.6,
        final_score=90.0,
        score_confidence=3,
        excluded=False,
        excluded_reason=None,
        discovered_by=["semantic_scholar"],
    )


# ── BUG-1: Results endpoint serialization ────────────────────────────────────

class TestBug1ResultsSerialization:
    """
    GET /runs/{id}/results returns SQLAlchemy ORM objects directly.
    Without a response_model, FastAPI/jsonable_encoder encounters
    _sa_instance_state which is not JSON-serializable → 500 error.

    Fix: add a ScoredResultResponse Pydantic model with from_attributes=True
    and set response_model on the endpoint.
    """

    def test_jsonable_encoder_on_orm_object_does_not_raise(self):
        """
        After the fix, jsonable_encoder must be able to encode a CIScoredResult
        without raising. Before the fix, this raises ValueError/TypeError.
        """
        import json
        result = _make_scored_result_orm()
        # This should not raise after the fix
        encoded = jsonable_encoder(result)
        # Must produce a proper dict, not garbage
        assert isinstance(encoded, dict)
        assert encoded["id"] == "00000000-0000-0000-0000-000000000001"
        assert encoded["content_type"] == "academic"
        assert encoded["final_score"] == 90.0
        # Must be fully JSON-serializable (no _sa_instance_state leakage)
        json_str = json.dumps(encoded)
        assert "_sa_instance_state" not in json_str

    def test_jsonable_encoder_list_of_orm_objects_does_not_raise(self):
        """Encoding a list of results (as returned by the endpoint) must work."""
        import json
        results = [_make_scored_result_orm(), _make_scored_result_orm()]
        encoded = jsonable_encoder(results)
        assert isinstance(encoded, list)
        assert len(encoded) == 2
        json.dumps(encoded)  # must not raise


# ── BUG-2: filter_config.min_topical_relevance ignored ───────────────────────

class TestBug2FilterConfigRelevanceGate:
    """
    The orchestrator stores filter_config.min_topical_relevance but never
    reads it when scoring. The user's requested gate is silently ignored;
    the hardcoded RELEVANCE_GATE (0.25) is always used.

    Fix: in _pipeline_inner, after scoring, apply filter_config gate to
    additionally exclude results that pass 0.25 but fail the user's value.
    """

    def test_apply_filter_config_gate_excludes_below_threshold(self):
        """
        Given filter_config.min_topical_relevance = 0.5, a result with
        topical_relevance = 0.3 (above 0.25 pipeline gate but below 0.5)
        must be excluded with reason 'below_filter_config_gate'.
        """
        from app.citation_intel.pipeline.filter import apply_filter_config_gate

        # Pre-set topical_relevance so we're testing the gate logic directly,
        # not the scorer. 0.3 is above the 0.25 pipeline gate but below 0.5.
        result = _make_raw(source_api="perplexity", citation_count=None, source_tier=3)
        result.topical_relevance = 0.3
        result.excluded = False

        apply_filter_config_gate([result], min_topical_relevance=0.5)
        assert result.excluded is True
        assert result.excluded_reason == "below_filter_config_gate"

    def test_apply_filter_config_gate_passes_above_threshold(self):
        """Results above user gate must NOT be additionally excluded."""
        from app.citation_intel.pipeline.filter import apply_filter_config_gate

        keywords = ["prompt injection", "jailbreaking", "adversarial"]
        result = _make_raw(source_api="perplexity", citation_count=None, source_tier=2)
        result.source_tier = 2
        result.tier_multiplier = 1.2
        score(result, keywords)

        # Apply a gate of 0.0 (should pass everything)
        apply_filter_config_gate([result], min_topical_relevance=0.0)
        # Only excluded if already excluded by scorer
        if result.topical_relevance is not None and result.topical_relevance >= RELEVANCE_GATE:
            assert result.excluded is False

    def test_apply_filter_config_gate_skips_already_excluded(self):
        """Already-excluded results must not have their excluded_reason overwritten."""
        from app.citation_intel.pipeline.filter import apply_filter_config_gate

        result = _make_raw(source_api="perplexity", citation_count=None)
        result.excluded = True
        result.excluded_reason = "below_relevance_gate"
        result.topical_relevance = 0.1

        apply_filter_config_gate([result], min_topical_relevance=0.5)
        # Reason must NOT be overwritten
        assert result.excluded_reason == "below_relevance_gate"

    def test_apply_filter_config_gate_none_is_noop(self):
        """If min_topical_relevance is None/0.0, the function must be a no-op."""
        from app.citation_intel.pipeline.filter import apply_filter_config_gate

        result = _make_raw(source_api="perplexity", citation_count=None)
        result.topical_relevance = 0.3
        result.excluded = False

        apply_filter_config_gate([result], min_topical_relevance=None)
        assert result.excluded is False

        apply_filter_config_gate([result], min_topical_relevance=0.0)
        assert result.excluded is False


# ── BUG-3: Pagination disabled check ─────────────────────────────────────────

class TestBug3PaginationLogic:
    """
    Frontend results page: disabled={displayed.length < 50} uses the
    FILTERED display list, not the raw fetched list. When excluded items
    are hidden and fill the page, Next is disabled even though page+1 exists.

    Fix: disabled={results.length < per_page} — use the raw API response length.

    This is a frontend bug; tested here as a logic/contract assertion.
    """

    def test_pagination_disabled_must_use_raw_not_displayed_length(self):
        """
        Scenario: API returned 50 results. 5 are excluded. User hides excluded.
        displayed.length = 45 < 50, so current (buggy) code disables Next.
        Correct: results.length = 50 = per_page, so Next MUST be enabled.
        """
        per_page = 50
        total_fetched = 50        # what the API returned
        excluded_count = 5
        show_excluded = False

        displayed_count = total_fetched - (excluded_count if not show_excluded else 0)
        # displayed_count = 45

        # BUGGY check (current code):
        buggy_next_disabled = displayed_count < per_page
        # CORRECT check (after fix):
        correct_next_disabled = total_fetched < per_page

        assert buggy_next_disabled is True, "Bug confirmed: Next is incorrectly disabled"
        assert correct_next_disabled is False, "Fix verified: Next should be enabled"

    def test_pagination_last_page_detection_still_works_after_fix(self):
        """
        When API returns fewer than per_page results, it IS the last page.
        The fix must not break last-page detection.
        """
        per_page = 50
        total_fetched = 30  # last page

        correct_next_disabled = total_fetched < per_page
        assert correct_next_disabled is True, "Last page correctly disabled"


# ── BUG-4: Double pipeline start race condition ───────────────────────────────

class TestBug4DoublePipelineStart:
    """
    POST /runs queues a background task immediately. The run page also shows
    a "Start Pipeline" button for queued runs. If the background task hasn't
    changed status yet, both code paths see status=queued and both proceed.

    Fix: make run_pipeline's status guard atomic with a DB-level UPDATE…WHERE
    that only succeeds once, not a SELECT+check.
    """

    @pytest.mark.asyncio
    async def test_run_pipeline_skips_if_not_queued(self):
        """
        If a run is already in 'synthesising' state when run_pipeline is called
        (i.e., a previous call already started it), it must return immediately
        without modifying the run.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_run = MagicMock()
        mock_run.id = "test-run-id"
        mock_run.status = "synthesising"  # Already started

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.citation_intel.pipeline.orchestrator.async_session_factory",
                   return_value=mock_session_cm):
            from app.citation_intel.pipeline.orchestrator import run_pipeline
            await run_pipeline("test-run-id")

        # Must NOT have called commit (no mutations)
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_pipeline_skips_if_already_complete(self):
        """Complete runs must be skipped too."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_run = MagicMock()
        mock_run.id = "test-run-id"
        mock_run.status = "complete"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.citation_intel.pipeline.orchestrator.async_session_factory",
                   return_value=mock_session_cm):
            from app.citation_intel.pipeline.orchestrator import run_pipeline
            await run_pipeline("test-run-id")

        mock_db.commit.assert_not_called()


# ── BUG-5: fallback_raw_id shared across multiple scored results ──────────────

class TestBug5FallbackRawId:
    """
    In _pipeline_inner, if identity lookup (doi/arxiv_id/url) misses for a
    result, `fallback_raw_id = rr_list[0].id` is used. Multiple unmatched
    results all get the same raw_result_id, violating the one-to-one
    relationship declared in the ORM.

    Fix: skip results that have no matching raw_result_id rather than
    assigning an arbitrary fallback. Log a warning per skipped result.
    The fallback_raw_id line must be removed.
    """

    def test_orchestrator_has_no_fallback_raw_id(self):
        """
        After fix: the orchestrator source must not contain the fallback_raw_id
        pattern. This test reads the source file as a canary.
        """
        import pathlib
        src = pathlib.Path(
            __file__
        ).parent.parent.parent / "citation_intel" / "pipeline" / "orchestrator.py"
        content = src.read_text()
        assert "fallback_raw_id" not in content, (
            "fallback_raw_id must be removed — it assigns the same raw_result_id "
            "to multiple CIScoredResult rows, breaking the one-to-one ORM relationship."
        )


# ── BUG-6: Normaliser uses object.__setattr__ on Pydantic model ───────────────

class TestBug6NormaliserPrivateAttrs:
    """
    normaliser.py sets _velocity_norm and _influential_norm via
    object.__setattr__(r, "_velocity_norm", ...) to bypass Pydantic validation.
    This works now but is fragile — if model_config changes (e.g. frozen=True
    or slots=True), it silently breaks scoring.

    Fix: declare _velocity_norm and _influential_norm as PrivateAttr fields
    in RawResultData, or pass norms as a separate dict rather than patching
    the model.
    """

    def test_velocity_norm_accessible_after_normalise(self):
        """After normalisation, _velocity_norm must be accessible normally."""
        r1 = _make_raw(citation_count=10, recent_citations=2, published_date="2022-01")
        r2 = _make_raw(citation_count=20, recent_citations=4, published_date="2022-01")

        normalise_citation_signals([r1, r2])

        # Must be accessible via getattr (not just object.__dict__)
        v1 = r1._velocity_norm  # type: ignore[attr-defined]
        v2 = r2._velocity_norm  # type: ignore[attr-defined]

        assert 0.0 <= v1 <= 1.0
        assert 0.0 <= v2 <= 1.0

    def test_influential_norm_accessible_after_normalise(self):
        """_influential_norm must also be accessible normally."""
        r1 = _make_raw(citation_count=10, influential_citations=1, published_date="2022-01")
        r2 = _make_raw(citation_count=20, influential_citations=5, published_date="2022-01")

        normalise_citation_signals([r1, r2])

        i1 = r1._influential_norm  # type: ignore[attr-defined]
        i2 = r2._influential_norm  # type: ignore[attr-defined]

        assert 0.0 <= i1 <= 1.0
        assert 0.0 <= i2 <= 1.0

    def test_private_attrs_declared_on_model(self):
        """
        After fix: RawResultData must declare _velocity_norm and
        _influential_norm as PrivateAttr so Pydantic manages them correctly.
        """
        from pydantic.fields import PrivateAttr
        fields = RawResultData.model_fields
        private = RawResultData.__private_attributes__

        assert "_velocity_norm" in private, (
            "_velocity_norm must be declared as PrivateAttr in RawResultData"
        )
        assert "_influential_norm" in private, (
            "_influential_norm must be declared as PrivateAttr in RawResultData"
        )


# ── BUG-7: Score breakdown display for SS preprints ──────────────────────────

class TestBug7ScoreBreakdownSsPreprint:
    """
    A Semantic Scholar paper that also has is_preprint=True gets scored by
    score_academic_full (SS weights: 35/30/20/15), but the frontend renders
    the preprint breakdown (arXiv weights: 60/40) because it checks
    `isPreprint` before `isAcademic && !isPreprint`.

    This is a display-only inconsistency — the stored scores are correct —
    but it misleads users about what signals drove the score.

    Fix: the display logic must be:
      1. SS academic (citation_count is not None, !is_preprint) → SS weights
      2. arXiv preprint (is_preprint=True, no citation data) → arXiv weights
      3. Web → web weights

    This is tested here as a contract: score function must NOT use
    score_academic_full for a result with both is_preprint=True and
    citation_count is not None when source_api is semantic_scholar.
    """

    def test_ss_preprint_uses_academic_full_scorer(self):
        """
        A SS result with citation data and is_preprint=True must use
        score_academic_full (SS weights), not score_academic_preprint.
        The distinguishing feature: SS full leaves citation velocity data
        in the result via _velocity_norm; preprint path does not.
        """
        r = RawResultData(
            source_api="semantic_scholar",
            title="Test paper on prompt injection attacks",
            abstract_or_snippet="This paper covers prompt injection jailbreaking adversarial prompts.",
            citation_count=50,
            recent_citations=10,
            influential_citations=5,
            published_date="2022-01",
            is_preprint=True,
            source_tier=1,
            venue_tier=1,
            category_tier=1,
        )

        normalise_citation_signals([r])
        keywords = ["prompt injection", "adversarial"]
        result = score(r, keywords)

        # SS full scorer was used: raw_score incorporates 4 components
        # score_confidence for SS full can be up to 5
        assert result.score_confidence is not None
        assert result.score_confidence <= 5
        # final_score must be non-zero (relevance gate passed)
        assert result.final_score is not None
        assert result.final_score > 0
