"""Citation Intelligence tables — ci_clusters, ci_runs, ci_query_jobs,
ci_raw_results, ci_scored_results

Revision ID: 001
Revises: None
Create Date: 2026-03-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ci_clusters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("cluster_config", JSONB, nullable=False),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ci_clusters_created_at", "ci_clusters", ["created_at"])

    op.create_table(
        "ci_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cluster_id", sa.String(36), sa.ForeignKey("ci_clusters.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("cluster_config", JSONB, nullable=False),
        sa.Column("source_config", JSONB, nullable=False),
        sa.Column("filter_config", JSONB, nullable=True),
        sa.Column("total_discovered", sa.Integer, nullable=True),
        sa.Column("total_deduped", sa.Integer, nullable=True),
        sa.Column("total_scored", sa.Integer, nullable=True),
        sa.Column("subtopic_relevance_scores", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ci_runs_status", "ci_runs", ["status"])
    op.create_index("ix_ci_runs_created_at", "ci_runs", ["created_at"])
    op.create_index("ix_ci_runs_updated_at", "ci_runs", ["updated_at"])

    op.create_table(
        "ci_query_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("ci_runs.id"), nullable=False),
        sa.Column("subtopic", sa.String(300), nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("source_api", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("items_returned", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retries", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ci_query_jobs_run_id", "ci_query_jobs", ["run_id"])
    op.create_index("ix_ci_query_jobs_status", "ci_query_jobs", ["status"])

    op.create_table(
        "ci_raw_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("ci_runs.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("ci_query_jobs.id"), nullable=False),
        sa.Column("source_api", sa.String(50), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("doi", sa.String(200), nullable=True),
        sa.Column("arxiv_id", sa.String(50), nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("authors", ARRAY(sa.String), nullable=True),
        sa.Column("abstract_or_snippet", sa.Text, nullable=True),
        sa.Column("published_date", sa.String(20), nullable=True),
        sa.Column("venue", sa.String(500), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("dedup_key", sa.String(500), nullable=True),
        sa.Column("is_duplicate", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ci_raw_results_run_id", "ci_raw_results", ["run_id"])
    op.create_index("ix_ci_raw_results_dedup_key", "ci_raw_results", ["dedup_key"])
    op.create_index("ix_ci_raw_results_is_duplicate", "ci_raw_results", ["is_duplicate"])

    op.create_table(
        "ci_scored_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("ci_runs.id"), nullable=False),
        sa.Column(
            "raw_result_id",
            sa.String(36),
            sa.ForeignKey("ci_raw_results.id"),
            nullable=False,
        ),
        sa.Column("content_type", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("doi", sa.String(200), nullable=True),
        sa.Column("arxiv_id", sa.String(50), nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("authors", ARRAY(sa.String), nullable=True),
        sa.Column("abstract_or_snippet", sa.Text, nullable=True),
        sa.Column("published_date", sa.String(20), nullable=True),
        sa.Column("venue", sa.String(500), nullable=True),
        sa.Column("source_tier", sa.Integer, nullable=True),
        sa.Column("tier_multiplier", sa.Float, nullable=True),
        sa.Column("pillar", sa.String(300), nullable=True),
        sa.Column("cluster_name", sa.String(300), nullable=True),
        sa.Column("subtopic", sa.String(300), nullable=True),
        sa.Column("matched_keywords", ARRAY(sa.String), nullable=True),
        sa.Column("keyword_density", sa.Float, nullable=True),
        sa.Column("topical_relevance", sa.Float, nullable=True),
        sa.Column("citation_count", sa.Integer, nullable=True),
        sa.Column("citation_velocity", sa.Float, nullable=True),
        sa.Column("influential_citations", sa.Integer, nullable=True),
        sa.Column("venue_tier", sa.Integer, nullable=True),
        sa.Column("is_preprint", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("category_tier", sa.Integer, nullable=True),
        sa.Column("raw_score", sa.Float, nullable=True),
        sa.Column("final_score", sa.Float, nullable=True),
        sa.Column("score_confidence", sa.Integer, nullable=True),
        sa.Column("excluded", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("excluded_reason", sa.String(200), nullable=True),
        sa.Column("discovered_by", ARRAY(sa.String), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ci_scored_results_run_id", "ci_scored_results", ["run_id"])
    op.create_index("ix_ci_scored_results_final_score", "ci_scored_results", ["final_score"])
    op.create_index("ix_ci_scored_results_excluded", "ci_scored_results", ["excluded"])
    op.create_index("ix_ci_scored_results_content_type", "ci_scored_results", ["content_type"])


def downgrade() -> None:
    op.drop_table("ci_scored_results")
    op.drop_table("ci_raw_results")
    op.drop_table("ci_query_jobs")
    op.drop_table("ci_runs")
    op.drop_table("ci_clusters")
