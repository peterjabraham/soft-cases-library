"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { use } from "react";
import Link from "next/link";
import { Kicker } from "@/components/ui/kicker";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { getRun, getRunJobs, startRun } from "@/lib/api";
import type { Run, QueryJob, SourceConfig } from "@/lib/types";

// ── Constants ─────────────────────────────────────────────────────────────────

const STAGES = [
  "queued",
  "synthesising",
  "discovering",
  "deduplicating",
  "scoring",
  "complete",
] as const;

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued — waiting to start",
  synthesising: "Synthesising queries…",
  discovering: "Discovering sources…",
  deduplicating: "Deduplicating results…",
  scoring: "Scoring & ranking…",
  complete: "Complete",
  failed: "Failed",
};

const SOURCE_META: Record<keyof SourceConfig, { label: string; hint: string; color: string }> = {
  perplexity: {
    label: "Perplexity",
    hint: "Web & editorial · sonar-pro model",
    color: "text-violet-400",
  },
  semantic_scholar: {
    label: "Semantic Scholar",
    hint: "Academic papers · citation data",
    color: "text-blue-400",
  },
  arxiv: {
    label: "arXiv",
    hint: "Preprints · cs.AI / cs.CR / cs.LG",
    color: "text-green-400",
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function elapsed(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const secs = Math.round((end - start) / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** Estimate query count: subtopics × 2–3 per subtopic × enabled sources */
function estimateQueryCount(run: Run): { min: number; max: number; subtopics: number; sources: number } {
  const subtopics = run.cluster_config.clusters.flatMap((c) => c.subtopics).length;
  const sources = Object.values(run.source_config).filter(Boolean).length;
  return { min: subtopics * 2 * sources, max: subtopics * 3 * sources, subtopics, sources };
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SourceStatusRow({
  apiKey,
  enabled,
  jobs,
}: {
  apiKey: keyof SourceConfig;
  enabled: boolean;
  jobs: QueryJob[];
}) {
  const meta = SOURCE_META[apiKey];
  const done = jobs.filter((j) => j.status === "complete").length;
  const failed = jobs.filter((j) => j.status === "failed").length;
  const running = jobs.filter((j) => j.status === "running").length;
  const total = jobs.length;
  const items = jobs.reduce((s, j) => s + (j.items_returned || 0), 0);

  let statusChip: React.ReactNode;
  if (!enabled) {
    statusChip = <Chip variant="default">Disabled</Chip>;
  } else if (total === 0) {
    statusChip = (
      <span className="inline-flex items-center gap-1.5 text-xs text-muted">
        <span className="w-2 h-2 rounded-full border border-muted/50" />
        Pending
      </span>
    );
  } else if (running > 0) {
    statusChip = (
      <span className="inline-flex items-center gap-1.5 text-xs text-accent">
        <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
        Running
      </span>
    );
  } else if (done + failed === total && failed > 0) {
    statusChip = <Chip variant="warning">⚠ Partial ({failed} failed)</Chip>;
  } else if (done === total && total > 0) {
    statusChip = <Chip variant="success">✓ Done</Chip>;
  } else {
    statusChip = <Chip variant="accent">Queued</Chip>;
  }

  return (
    <div className={`flex items-start justify-between gap-3 py-2.5 border-b border-border last:border-0 ${!enabled ? "opacity-40" : ""}`}>
      <div>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${meta.color}`}>{meta.label}</span>
        </div>
        <p className="text-xs text-muted mt-0.5">{meta.hint}</p>
        {/* Per-job errors */}
        {jobs.filter((j) => j.error_message).map((j) => (
          <p key={j.id} className="text-xs text-red-400 mt-1 font-mono">
            ✗ {j.subtopic}: {j.error_message}
          </p>
        ))}
      </div>
      <div className="text-right shrink-0">
        {statusChip}
        {total > 0 && (
          <p className="text-xs text-muted mt-1 font-mono">
            {done}/{total} jobs · {items > 0 ? `${items} found` : "0 found"}
          </p>
        )}
      </div>
    </div>
  );
}

function RunPlan({ run }: { run: Run }) {
  const est = estimateQueryCount(run);

  return (
    <Card padding="lg" className="mb-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-base font-bold text-foreground">What will be searched</h2>
          <p className="text-xs text-muted mt-0.5">
            {est.subtopics} subtopic{est.subtopics !== 1 ? "s" : ""} ·{" "}
            ~{est.min}–{est.max} queries across {est.sources} source
            {est.sources !== 1 ? "s" : ""}
          </p>
        </div>
        <Chip variant="default" className="shrink-0">
          {run.cluster_config.pillar}
        </Chip>
      </div>

      {/* Subtopics */}
      <div className="space-y-4">
        {run.cluster_config.clusters.map((cluster) => (
          <div key={cluster.name}>
            <p className="text-xs text-muted uppercase tracking-wider mb-2">{cluster.name}</p>
            <div className="space-y-2">
              {cluster.subtopics.map((sub) => (
                <div key={sub.name} className="pl-3 border-l border-border">
                  <p className="text-sm font-medium text-foreground">{sub.name}</p>
                  <p className="text-xs text-muted mt-0.5 leading-relaxed">
                    {sub.keywords.join(", ")}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

interface Props {
  params: Promise<{ id: string }>;
}

export default function RunPage({ params }: Props) {
  const { id } = use(params);

  const [run, setRun] = useState<Run | null>(null);
  const [jobs, setJobs] = useState<QueryJob[]>([]);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchState = useCallback(async () => {
    try {
      const [runData, jobData] = await Promise.all([getRun(id), getRunJobs(id)]);
      setRun(runData);
      setJobs(jobData);
      if (runData.status === "complete" || runData.status === "failed") {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    } catch (e: unknown) {
      setFetchError(e instanceof Error ? e.message : "Failed to load run");
    }
  }, [id]);

  const handleStart = useCallback(async () => {
    if (!run || run.status !== "queued") return;
    setStarting(true);
    setStartError(null);
    try {
      await startRun(id);
      // fetchState immediately to reflect the status change
      await fetchState();
    } catch (e: unknown) {
      setStartError(e instanceof Error ? e.message : "Failed to start run");
    } finally {
      setStarting(false);
    }
  }, [run, id, fetchState]);

  useEffect(() => {
    fetchState();
    pollRef.current = setInterval(fetchState, 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchState]);

  const currentStageIdx = run ? STAGES.indexOf(run.status as typeof STAGES[number]) : -1;
  const isRunning = run && run.status !== "complete" && run.status !== "failed";

  // Group jobs by source API for SourceStatusRow
  const jobsByApi = jobs.reduce<Record<string, QueryJob[]>>((acc, job) => {
    if (!acc[job.source_api]) acc[job.source_api] = [];
    acc[job.source_api].push(job);
    return acc;
  }, {});

  if (fetchError) {
    return (
      <div className="py-12 max-w-2xl mx-auto">
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg mb-4">
          <p className="text-sm font-medium text-red-400 mb-1">Could not load run</p>
          <p className="text-xs text-red-400/80 font-mono">{fetchError}</p>
        </div>
        <Link href="/" className="text-sm text-muted hover:text-accent">← Back to New Run</Link>
      </div>
    );
  }

  return (
    <div className="py-12 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Kicker>Citation Intelligence · Pipeline</Kicker>
        <h1 className="text-2xl font-black tracking-tight mb-1">Discovery Run</h1>
        <p className="text-xs text-muted font-mono">{id}</p>
      </div>

      {/* Loading skeleton */}
      {!run && !fetchError && (
        <Card padding="lg" className="mb-6">
          <div className="flex items-center gap-3 text-muted">
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Loading run…</span>
          </div>
        </Card>
      )}

      {run && (
        <>
          {/* ── Stage progress ──────────────────────────────────── */}
          <Card padding="lg" className="mb-6">
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <CardTitle>{STAGE_LABELS[run.status] || run.status}</CardTitle>
                  <CardDescription className="mt-0.5">
                    {run.cluster_config.pillar} · {run.cluster_config.clusters.length} cluster
                    {run.cluster_config.clusters.length !== 1 ? "s" : ""}
                  </CardDescription>
                </div>

                {/* Live indicator while running */}
                {isRunning && run.status !== "queued" && (
                  <div className="flex items-center gap-1.5 text-xs text-accent shrink-0 mt-1">
                    <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                    Live
                  </div>
                )}

                {/* Start button — only shown in queued state */}
                {run.status === "queued" && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleStart}
                    disabled={starting}
                    className="shrink-0"
                  >
                    {starting ? (
                      <span className="flex items-center gap-1.5">
                        <span className="w-3 h-3 border border-white/50 border-t-transparent rounded-full animate-spin" />
                        Starting…
                      </span>
                    ) : (
                      "▶ Start Pipeline"
                    )}
                  </Button>
                )}
              </div>

              {/* Start error */}
              {startError && (
                <p className="text-xs text-red-400 mt-2 font-mono">{startError}</p>
              )}
            </CardHeader>

            <div className="space-y-2">
              {STAGES.map((stage, idx) => {
                const stageIdx = STAGES.indexOf(stage);
                const isComplete = run.status === "complete" ? true : stageIdx < currentStageIdx;
                const isCurrent = stageIdx === currentStageIdx;
                const isFailed = run.status === "failed" && isCurrent;

                return (
                  <div key={stage} className="flex items-center gap-3">
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono shrink-0 ${
                        isFailed
                          ? "bg-red-500/20 text-red-400 border border-red-500/30"
                          : isComplete
                            ? "bg-green-500/20 text-green-400 border border-green-500/30"
                            : isCurrent
                              ? "bg-accent/20 text-accent border border-accent/30 animate-pulse"
                              : "bg-card border border-border text-muted"
                      }`}
                    >
                      {isComplete ? "✓" : isFailed ? "✗" : idx + 1}
                    </div>
                    <span
                      className={`text-sm ${
                        isCurrent ? "text-foreground font-medium"
                          : isComplete ? "text-green-400"
                          : "text-muted"
                      }`}
                    >
                      {STAGE_LABELS[stage]}
                    </span>
                    {isCurrent && isRunning && stage !== "queued" && (
                      <span className="text-xs text-muted animate-pulse">processing…</span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Timing + counters */}
            <div className="mt-4 pt-4 border-t border-border flex flex-wrap gap-4 text-xs text-muted">
              <span>Created: {formatTime(run.created_at)}</span>
              {run.started_at && (
                <>
                  <span>Started: {formatTime(run.started_at)}</span>
                  <span>Elapsed: {elapsed(run.started_at, run.completed_at)}</span>
                </>
              )}
              {run.total_discovered != null && <span>Discovered: {run.total_discovered}</span>}
              {run.total_deduped != null && <span>After dedup: {run.total_deduped}</span>}
              {run.total_scored != null && <span>Scored: {run.total_scored}</span>}
            </div>
          </Card>

          {/* ── Sources panel — always visible ──────────────────── */}
          <Card padding="lg" className="mb-6">
            <h2 className="text-base font-bold text-foreground mb-1">Sources</h2>
            <p className="text-xs text-muted mb-3">
              {jobs.length > 0
                ? `${jobs.length} quer${jobs.length !== 1 ? "ies" : "y"} across ${new Set(jobs.map((j) => j.subtopic)).size} subtopics`
                : "Queries will be generated when the pipeline starts"}
            </p>
            <div>
              {(Object.keys(SOURCE_META) as (keyof SourceConfig)[]).map((apiKey) => (
                <SourceStatusRow
                  key={apiKey}
                  apiKey={apiKey}
                  enabled={!!run.source_config[apiKey]}
                  jobs={jobsByApi[apiKey] || []}
                />
              ))}
            </div>

            {/* Live job breakdown — only shows once pipeline has started */}
            {jobs.length > 0 && (
              <details className="mt-3">
                <summary className="text-xs text-muted cursor-pointer hover:text-accent select-none">
                  Show all {jobs.length} query jobs
                </summary>
                <div className="mt-3 space-y-1 max-h-64 overflow-y-auto">
                  {jobs.map((job) => (
                    <div
                      key={job.id}
                      className={`flex items-start justify-between gap-2 py-1.5 text-xs border-b border-border/50 last:border-0 ${
                        job.status === "failed" ? "bg-red-500/5" : ""
                      }`}
                    >
                      <div className="min-w-0">
                        <span className="text-foreground truncate block">{job.subtopic}</span>
                        {job.error_message && (
                          <span className="text-red-400 font-mono text-xs block mt-0.5">
                            ✗ {job.error_message}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-muted">{SOURCE_META[job.source_api as keyof SourceConfig]?.label ?? job.source_api}</span>
                        <span
                          className={
                            job.status === "complete" ? "text-green-400"
                            : job.status === "failed" ? "text-red-400"
                            : job.status === "running" ? "text-accent"
                            : "text-muted"
                          }
                        >
                          {job.status === "complete"
                            ? `✓ ${job.items_returned ?? 0}`
                            : job.status === "failed"
                              ? "✗ failed"
                              : job.status === "running"
                                ? "◐ running"
                                : "○ queued"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </Card>

          {/* ── Run plan — always visible, replaced by live data when running ── */}
          <RunPlan run={run} />

          {/* ── Subtopic relevance warnings (post-run) ──────────── */}
          {run.subtopic_relevance_scores && (
            <Card className="mb-6">
              <h2 className="text-sm font-bold text-foreground mb-2">Subtopic Relevance</h2>
              <div className="space-y-1">
                {Object.entries(run.subtopic_relevance_scores).map(([name, score]) => (
                  <div key={name} className="flex items-center justify-between text-sm">
                    <span className={score < 0.30 ? "text-amber-400" : "text-foreground"}>
                      {score < 0.30 && "⚠ "}{name}
                    </span>
                    <span className="font-mono text-muted">{(score * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
              {Object.values(run.subtopic_relevance_scores).some((s) => s < 0.30) && (
                <p className="text-xs text-amber-400 mt-2">
                  ⚠ Low relevance — review keywords for flagged subtopics
                </p>
              )}
            </Card>
          )}

          {/* ── Complete ─────────────────────────────────────────── */}
          {run.status === "complete" && (
            <Card padding="lg" className="mb-6 border-green-500/30">
              <div className="flex items-center justify-between">
                <div>
                  <Chip variant="success" className="mb-2">Complete</Chip>
                  <p className="text-sm text-muted">
                    {run.total_scored != null && (
                      <>{run.total_scored} result{run.total_scored !== 1 ? "s" : ""} scored. </>
                    )}
                    Discovery finished successfully.
                  </p>
                </div>
                <Link href={`/runs/${id}/results`}>
                  <Button variant="primary" size="md">View Results →</Button>
                </Link>
              </div>
            </Card>
          )}

          {/* ── Failed ───────────────────────────────────────────── */}
          {run.status === "failed" && (
            <Card padding="lg" className="mb-6 border-red-500/30">
              <Chip variant="error" className="mb-3">Failed</Chip>
              {run.error_message ? (
                <div className="bg-background rounded-lg p-3">
                  <p className="text-xs text-muted mb-1 font-medium">Error detail</p>
                  <p className="text-xs text-red-400 font-mono whitespace-pre-wrap max-h-32 overflow-y-auto">
                    {run.error_message}
                  </p>
                </div>
              ) : (
                <p className="text-sm text-muted">
                  The pipeline failed without an error message. Check the backend logs.
                </p>
              )}
              <div className="mt-4 flex gap-3">
                <Link href="/">
                  <Button variant="primary" size="sm">← Start New Run</Button>
                </Link>
              </div>
            </Card>
          )}
        </>
      )}

      {/* Nav */}
      <div className="mt-4 flex items-center gap-4">
        <Link href="/" className="text-sm text-muted hover:text-accent transition-colors">
          ← New Run
        </Link>
        {run?.status === "complete" && (
          <Link href={`/runs/${id}/results`} className="text-sm text-accent hover:underline">
            View Results →
          </Link>
        )}
      </div>
    </div>
  );
}
