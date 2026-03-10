"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { Kicker } from "@/components/ui/kicker";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { getResults, getRun, exportCsvUrl, exportJsonUrl } from "@/lib/api";
import type { Run, ScoredResult } from "@/lib/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function tierLabel(tier: number | null): string {
  if (!tier) return "—";
  return `T${tier}`;
}

function tierColor(tier: number | null): string {
  if (!tier) return "text-muted";
  return tier === 1
    ? "text-blue-400"
    : tier === 2
      ? "text-accent"
      : tier === 3
        ? "text-foreground"
        : "text-muted";
}

function scoreColor(score: number | null): string {
  if (score === null) return "text-muted";
  if (score >= 75) return "text-green-400";
  if (score >= 50) return "text-amber-400";
  if (score >= 25) return "text-foreground";
  return "text-muted";
}

function ConfidenceDots({ value, max }: { value: number | null; max: number }) {
  const filled = value ?? 0;
  return (
    <span
      className="inline-flex gap-0.5 items-center"
      title={`${filled}/${max} signals available`}
    >
      {Array.from({ length: max }, (_, i) => (
        <span
          key={i}
          className={`w-1.5 h-1.5 rounded-full ${i < filled ? "bg-accent" : "bg-border"}`}
        />
      ))}
    </span>
  );
}

function ContentTypeChip({ type }: { type: string }) {
  const variants: Record<string, "accent" | "success" | "warning" | "default"> = {
    academic: "accent",
    news: "success",
    blog: "warning",
    unknown: "default",
  };
  return <Chip variant={variants[type] ?? "default"}>{type}</Chip>;
}

function ScoreBreakdown({ result }: { result: ScoredResult }) {
  const isAcademic = result.content_type === "academic";
  const isPreprint = result.is_preprint;

  return (
    <div className="mt-3 pt-3 border-t border-border space-y-2">
      {/* Abstract */}
      {result.abstract_or_snippet && (
        <p className="text-xs text-muted leading-relaxed">
          {result.abstract_or_snippet.slice(0, 400)}
          {result.abstract_or_snippet.length > 400 ? "…" : ""}
        </p>
      )}

      {/* Score breakdown */}
      <div className="bg-background rounded-lg p-3 space-y-1">
        <p className="text-xs text-muted font-medium mb-1">Score breakdown</p>

        {isAcademic && !isPreprint && (
          <>
            <ScoreLine label="Topical relevance" value={result.topical_relevance} weight={0.35} />
            <ScoreLine label="Citation velocity" value={null} weight={0.30} note="normalised within run" />
            <ScoreLine label="Influential citations" value={null} weight={0.20} note={`${result.influential_citations ?? "—"} total`} />
            <ScoreLine label="Venue tier" value={result.venue_tier ? result.venue_tier === 1 ? 1.0 : 0.5 : null} weight={0.15} />
          </>
        )}
        {isPreprint && (
          <>
            <ScoreLine label="Topical relevance" value={result.topical_relevance} weight={0.60} />
            <ScoreLine label="Category tier" value={result.category_tier === 1 ? 1.0 : 0.5} weight={0.40} note={result.arxiv_categories?.join(", ") ?? ""} />
          </>
        )}
        {!isAcademic && (
          <>
            <ScoreLine label="Topical relevance" value={result.topical_relevance} weight={0.70} />
            <ScoreLine label="Source tier score" value={tierToScore(result.source_tier)} weight={0.30} note={tierLabel(result.source_tier)} />
          </>
        )}

        <div className="pt-1 mt-1 border-t border-border/50 text-xs text-muted font-mono">
          raw {result.raw_score?.toFixed(3) ?? "—"} × {result.tier_multiplier?.toFixed(1) ?? "—"} × 100 ={" "}
          <span className={`font-bold ${scoreColor(result.final_score)}`}>
            {result.final_score?.toFixed(1) ?? "—"}
          </span>
          {result.is_preprint && (
            <span className="ml-2 text-amber-400">⚠ preprint — confidence capped 3/5</span>
          )}
        </div>
      </div>

      {/* Meta */}
      <div className="flex flex-wrap gap-3 text-xs text-muted">
        {result.matched_keywords && result.matched_keywords.length > 0 && (
          <span>
            Matched: {result.matched_keywords.slice(0, 5).join(", ")}
            {result.matched_keywords.length > 5 && ` +${result.matched_keywords.length - 5}`}
          </span>
        )}
        {result.subtopic && <span>Subtopic: {result.subtopic}</span>}
        {result.discovered_by && (
          <span>Via: {result.discovered_by.join(", ")}</span>
        )}
        {result.citation_count != null && (
          <span>{result.citation_count.toLocaleString()} citations</span>
        )}
      </div>

      {/* Excluded warning */}
      {result.excluded && (
        <p className="text-xs text-amber-400">
          ⚠ Excluded: {result.excluded_reason ?? "below relevance gate"}
        </p>
      )}
    </div>
  );
}

function ScoreLine({
  label,
  value,
  weight,
  note,
}: {
  label: string;
  value: number | null;
  weight: number;
  note?: string;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted w-36 shrink-0">{label}</span>
      <span className="font-mono text-foreground w-10">
        {value !== null ? value.toFixed(2) : "—"}
      </span>
      <span className="text-muted">× {weight.toFixed(2)}</span>
      {note && <span className="text-muted/60">{note}</span>}
    </div>
  );
}

function tierToScore(tier: number | null): number | null {
  const map: Record<number, number> = { 1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25, 5: 0.0 };
  return tier ? map[tier] ?? null : null;
}

// ── Main page ─────────────────────────────────────────────────────────────────

interface Props {
  params: Promise<{ id: string }>;
}

export default function ResultsPage({ params }: Props) {
  const { id } = use(params);

  const [run, setRun] = useState<Run | null>(null);
  const [results, setResults] = useState<ScoredResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showExcluded, setShowExcluded] = useState(false);

  // Filters
  const [contentType, setContentType] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [sourceTier, setSourceTier] = useState("");
  const [subtopic, setSubtopic] = useState("");
  const [sort, setSort] = useState<"final_score" | "citation_count" | "published_date" | "topical_relevance">("final_score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  const uniqueSubtopics = run
    ? Array.from(
        new Set(
          run.cluster_config.clusters.flatMap((c) => c.subtopics.map((s) => s.name)),
        ),
      )
    : [];

  const fetchResults = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getResults(id, {
        content_type: contentType || undefined,
        min_score: minScore > 0 ? minScore : undefined,
        source_tier: sourceTier || undefined,
        subtopic: subtopic || undefined,
        sort,
        order,
        page,
        per_page: 50,
      });
      setResults(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load results");
    } finally {
      setLoading(false);
    }
  }, [id, contentType, minScore, sourceTier, subtopic, sort, order, page]);

  useEffect(() => {
    getRun(id)
      .then(setRun)
      .catch(() => {});
    fetchResults();
  }, [id, fetchResults]);

  const displayed = showExcluded ? results : results.filter((r) => !r.excluded);
  const excludedCount = results.filter((r) => r.excluded).length;

  return (
    <div className="py-12">
      {/* Header */}
      <div className="mb-6">
        <Kicker>Citation Intelligence · Results</Kicker>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black tracking-tight mb-1">
              {run?.cluster_config.pillar ?? "Discovery Results"}
            </h1>
            <p className="text-sm text-muted font-mono">{id}</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <a href={exportCsvUrl(id)} target="_blank" rel="noreferrer">
              <Button variant="default" size="sm">Export CSV</Button>
            </a>
            <a href={exportJsonUrl(id)} target="_blank" rel="noreferrer">
              <Button variant="default" size="sm">Export JSON</Button>
            </a>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      {run && (
        <div className="bg-card border border-border rounded-lg p-4 mb-6">
          <div className="flex flex-wrap items-center gap-6 text-sm">
            <StatItem label="Discovered" value={run.total_discovered} />
            <Divider />
            <StatItem label="After dedup" value={run.total_deduped} />
            <Divider />
            <StatItem label="Scored" value={run.total_scored} />
            <Divider />
            <StatItem label="Shown" value={displayed.length} />
            {excludedCount > 0 && (
              <>
                <Divider />
                <button
                  onClick={() => setShowExcluded((v) => !v)}
                  className="text-muted hover:text-accent text-sm transition-colors"
                >
                  {showExcluded ? "Hide" : "Show"} excluded ({excludedCount})
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="bg-card border border-border rounded-lg p-4 mb-4">
        <div className="flex flex-wrap gap-3 items-end">
          {/* Content type */}
          <div>
            <label className="text-xs text-muted block mb-1">Type</label>
            <select
              value={contentType}
              onChange={(e) => { setContentType(e.target.value); setPage(1); }}
              className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <option value="">All types</option>
              <option value="academic">Academic</option>
              <option value="news">News</option>
              <option value="blog">Blog</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>

          {/* Source tier */}
          <div>
            <label className="text-xs text-muted block mb-1">Tier</label>
            <select
              value={sourceTier}
              onChange={(e) => { setSourceTier(e.target.value); setPage(1); }}
              className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <option value="">All tiers</option>
              <option value="1">T1 (Top academic)</option>
              <option value="2">T2 (Quality news / labs)</option>
              <option value="3">T3 (Practitioners)</option>
              <option value="4,5">T4-5 (Other)</option>
            </select>
          </div>

          {/* Subtopic */}
          {uniqueSubtopics.length > 0 && (
            <div>
              <label className="text-xs text-muted block mb-1">Subtopic</label>
              <select
                value={subtopic}
                onChange={(e) => { setSubtopic(e.target.value); setPage(1); }}
                className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
              >
                <option value="">All subtopics</option>
                {uniqueSubtopics.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          )}

          {/* Min score */}
          <div>
            <label className="text-xs text-muted block mb-1">Min score: {minScore}</label>
            <input
              type="range"
              min={0}
              max={80}
              step={10}
              value={minScore}
              onChange={(e) => { setMinScore(Number(e.target.value)); setPage(1); }}
              className="w-28 accent-accent"
            />
          </div>

          {/* Sort */}
          <div>
            <label className="text-xs text-muted block mb-1">Sort</label>
            <select
              value={`${sort}:${order}`}
              onChange={(e) => {
                const [s, o] = e.target.value.split(":") as [typeof sort, typeof order];
                setSort(s);
                setOrder(o);
                setPage(1);
              }}
              className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <option value="final_score:desc">Score ↓</option>
              <option value="final_score:asc">Score ↑</option>
              <option value="citation_count:desc">Citations ↓</option>
              <option value="topical_relevance:desc">Relevance ↓</option>
              <option value="published_date:desc">Date ↓</option>
            </select>
          </div>

          <Button variant="ghost" size="sm" onClick={fetchResults}>
            Apply
          </Button>
        </div>

        {/* Confidence disclaimer */}
        <p className="text-xs text-muted/70 mt-3">
          ● = signal present · ○ = signal absent · Web content confidence capped at 2/5 (no DA/backlinks) —
          lower confidence ≠ lower quality for Claim Sets.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg mb-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-3 text-muted py-8">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading results…</span>
        </div>
      )}

      {/* Results table */}
      {!loading && displayed.length === 0 && (
        <Card padding="lg">
          <p className="text-sm text-muted text-center py-4">
            No results match the current filters.
          </p>
        </Card>
      )}

      {!loading && displayed.length > 0 && (
        <div className="space-y-2">
          {displayed.map((result, idx) => (
            <div
              key={result.id}
              className={`bg-card border rounded-lg transition-colors ${
                result.excluded
                  ? "border-amber-500/20 opacity-60"
                  : expandedId === result.id
                    ? "border-accent/40"
                    : "border-border hover:border-border/80"
              }`}
            >
              {/* Row */}
              <button
                className="w-full text-left p-4"
                onClick={() =>
                  setExpandedId(expandedId === result.id ? null : result.id)
                }
              >
                <div className="flex items-start gap-3">
                  {/* Index */}
                  <span className="text-xs text-muted font-mono w-5 shrink-0 mt-0.5">
                    {idx + 1}
                  </span>

                  {/* Main content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start gap-2 flex-wrap mb-1">
                      <ContentTypeChip type={result.content_type} />
                      <span className={`text-xs font-mono font-bold ${tierColor(result.source_tier)}`}>
                        {tierLabel(result.source_tier)}
                      </span>
                      {result.is_preprint && (
                        <Chip variant="warning" className="text-xs">preprint</Chip>
                      )}
                    </div>

                    <p className="text-sm font-medium text-foreground leading-snug mb-1">
                      {result.title || result.url || "Untitled"}
                    </p>

                    <div className="flex flex-wrap gap-3 text-xs text-muted">
                      {result.venue && <span>{result.venue}</span>}
                      {result.published_date && <span>{result.published_date.slice(0, 4)}</span>}
                      {result.authors && result.authors.length > 0 && (
                        <span>
                          {result.authors.slice(0, 2).join(", ")}
                          {result.authors.length > 2 && ` +${result.authors.length - 2}`}
                        </span>
                      )}
                        {result.url && (() => {
                          try {
                            const hostname = new URL(result.url).hostname.replace("www.", "");
                            return (
                              <a
                                href={result.url}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="text-accent hover:underline truncate max-w-xs"
                              >
                                {hostname}
                              </a>
                            );
                          } catch {
                            return (
                              <span className="text-muted truncate max-w-xs">{result.url}</span>
                            );
                          }
                        })()}
                    </div>
                  </div>

                  {/* Score + confidence */}
                  <div className="shrink-0 text-right">
                    <div
                      className={`text-xl font-black tabular-nums ${scoreColor(result.final_score)}`}
                    >
                      {result.final_score?.toFixed(0) ?? "—"}
                    </div>
                    <ConfidenceDots value={result.score_confidence} max={5} />
                  </div>
                </div>
              </button>

              {/* Expanded */}
              {expandedId === result.id && (
                <div className="px-4 pb-4">
                  <ScoreBreakdown result={result} />
                </div>
              )}
            </div>
          ))}

          {/* Pagination */}
          <div className="flex items-center justify-between pt-4">
            <Button
              variant="ghost"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              ← Previous
            </Button>
            <span className="text-xs text-muted">Page {page}</span>
            <Button
              variant="ghost"
              size="sm"
              disabled={results.length < 50}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </Button>
          </div>
        </div>
      )}

      {/* Nav */}
      <div className="mt-8 flex gap-4">
        <Link
          href={`/runs/${id}`}
          className="text-sm text-muted hover:text-accent transition-colors"
        >
          ← Back to Pipeline
        </Link>
        <Link href="/" className="text-sm text-muted hover:text-accent transition-colors">
          New Run
        </Link>
      </div>
    </div>
  );
}

function StatItem({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div>
      <span className="text-muted">{label}</span>{" "}
      <span className="font-mono tabular-nums text-foreground">
        {value != null ? value.toLocaleString() : "—"}
      </span>
    </div>
  );
}

function Divider() {
  return <div className="w-px h-4 bg-border hidden sm:block" />;
}
