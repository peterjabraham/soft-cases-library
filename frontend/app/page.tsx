"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Kicker } from "@/components/ui/kicker";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Textarea } from "@/components/ui/input";
import { createRun, generateClusterFromTopic, listClusters, saveCluster } from "@/lib/api";
import type { ClusterConfig, SavedCluster, SourceConfig } from "@/lib/types";

const EXAMPLE_CLUSTER: ClusterConfig = {
  pillar: "AI Security",
  clusters: [
    {
      name: "Prompt Injection",
      subtopics: [
        {
          name: "Attack Vectors & Techniques",
          keywords: ["prompt injection", "jailbreaking", "adversarial prompts", "indirect prompt injection"],
        },
        {
          name: "Defence & Mitigation",
          keywords: ["prompt injection defense", "input sanitization LLM", "dual LLM pattern", "CaMeL prompt injection"],
        },
        {
          name: "Risks in Production Systems",
          keywords: ["LLM agent security", "RAG prompt injection", "MCP security vulnerabilities", "tool use security"],
        },
      ],
    },
  ],
};

const SOURCE_LABELS: Record<keyof SourceConfig, { label: string; hint: string }> = {
  perplexity: { label: "Perplexity", hint: "Web & editorial discovery" },
  semantic_scholar: { label: "Semantic Scholar", hint: "Academic papers (free)" },
  arxiv: { label: "arXiv", hint: "Preprints (free, no key needed)" },
};

export default function QueryConfigPage() {
  const router = useRouter();

  const [clusterJson, setClusterJson] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsedCluster, setParsedCluster] = useState<ClusterConfig | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [selectedSubtopics, setSelectedSubtopics] = useState<Set<string>>(new Set());
  const [sources, setSources] = useState<SourceConfig>({
    perplexity: true,
    semantic_scholar: true,
    arxiv: true,
  });

  const [minScore, setMinScore] = useState(0);
  const [clusterName, setClusterName] = useState("");
  const [savedClusters, setSavedClusters] = useState<SavedCluster[]>([]);
  const [topicInput, setTopicInput] = useState("");
  const [generatingCluster, setGeneratingCluster] = useState(false);
  const [generationInfo, setGenerationInfo] = useState<string>("");

  const [submitting, setSubmitting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listClusters()
      .then(setSavedClusters)
      .catch(() => {});
  }, []);

  const parseJson = useCallback((value: string) => {
    setClusterJson(value);
    try {
      const parsed = JSON.parse(value);
      if (!parsed.pillar || !Array.isArray(parsed.clusters) || parsed.clusters.length === 0) {
        setParseError('Must have "pillar" and at least one cluster.');
        setParsedCluster(null);
        return;
      }
      for (const c of parsed.clusters) {
        if (!c.name || !Array.isArray(c.subtopics) || c.subtopics.length === 0) {
          setParseError(`Cluster "${c.name || "(unnamed)"}" must have at least one subtopic.`);
          setParsedCluster(null);
          return;
        }
        for (const s of c.subtopics) {
          if (!s.keywords || s.keywords.length < 2) {
            setParseError(`Subtopic "${s.name}" needs at least 2 keywords.`);
            setParsedCluster(null);
            return;
          }
        }
      }
      setParseError(null);
      const newCluster = parsed as ClusterConfig;
      setParsedCluster(newCluster);
      // Auto-select all subtopics on valid parse
      setSelectedSubtopics(
        new Set(newCluster.clusters.flatMap((c) => c.subtopics.map((s) => s.name))),
      );
    } catch {
      setParseError("Invalid JSON — check formatting.");
      setParsedCluster(null);
    }
  }, []);

  const loadSavedCluster = (cluster: SavedCluster) => {
    const json = JSON.stringify(cluster.cluster_config, null, 2);
    setClusterJson(json);
    parseJson(json);
    setClusterName(cluster.name);
    setShowAdvanced(true);
  };

  const allSubtopics = parsedCluster
    ? parsedCluster.clusters.flatMap((c) =>
        c.subtopics.map((s) => ({ cluster: c.name, subtopic: s })),
      )
    : [];

  const toggleSubtopic = (name: string) => {
    setSelectedSubtopics((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const toggleSource = (key: keyof SourceConfig) => {
    setSources((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const anySourceEnabled = Object.values(sources).some(Boolean);
  const anySubtopicSelected = selectedSubtopics.size > 0;
  const canRun = parsedCluster && !parseError && anySourceEnabled && anySubtopicSelected;

  const handleSaveCluster = async () => {
    if (!parsedCluster || !clusterName.trim()) return;
    setSaving(true);
    try {
      const saved = await saveCluster(clusterName.trim(), parsedCluster);
      setSavedClusters((prev) => [saved, ...prev]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleStartRun = async () => {
    if (!parsedCluster || !canRun) return;
    setError("");
    setSubmitting(true);

    // Filter cluster to selected subtopics
    const filteredConfig: ClusterConfig = {
      ...parsedCluster,
      clusters: parsedCluster.clusters
        .map((c) => ({
          ...c,
          subtopics: c.subtopics.filter((s) => selectedSubtopics.has(s.name)),
        }))
        .filter((c) => c.subtopics.length > 0),
    };

    try {
      const run = await createRun(filteredConfig, sources, undefined, {
        min_topical_relevance: minScore / 100,
      });
      router.push(`/runs/${run.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start run");
      setSubmitting(false);
    }
  };

  const handleGenerateCluster = async () => {
    const topic = topicInput.trim();
    if (topic.length < 3) {
      setError("Enter a topic with at least 3 characters.");
      return;
    }
    setError("");
    setGenerationInfo("");
    setGeneratingCluster(true);
    try {
      const generated = await generateClusterFromTopic(topic);
      const json = JSON.stringify(generated.cluster_config, null, 2);
      parseJson(json);
      setClusterName(topic);
      setGenerationInfo(
        `Generated with ${generated.model}. Review and edit before starting discovery.`,
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate cluster");
    } finally {
      setGeneratingCluster(false);
    }
  };

  return (
    <div className="py-12">
      {/* Header */}
      <div className="mb-8">
        <Kicker>Soft-Cases · Citation Intelligence</Kicker>
        <h1 className="text-3xl font-black tracking-tight mb-3">
          Source Discovery
        </h1>
        <p className="text-base text-muted max-w-2xl">
          Define a topic cluster, choose your sources, and start the discovery pipeline.
          Scores authoritative sources for Claim Set research.
        </p>
      </div>

      {/* Saved clusters */}
      {savedClusters.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-muted uppercase tracking-wider mb-2">Saved Clusters</p>
          <div className="flex flex-wrap gap-2">
            {savedClusters.map((sc) => (
              <button
                key={sc.id}
                onClick={() => loadSavedCluster(sc)}
                className="px-3 py-1.5 text-xs border border-border rounded-lg bg-card text-foreground hover:border-accent hover:text-accent transition-colors"
              >
                {sc.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── Left: Cluster Config ─────────────────────────────────── */}
        <div className="space-y-4">
          <Card padding="lg">
            <div className="flex items-start justify-between mb-3 gap-3">
              <div>
                <h2 className="text-base font-bold text-foreground">
                  New to cluster JSON?
                </h2>
                <p className="text-xs text-muted mt-1">
                  Enter your topic and generate a starter cluster draft. You can edit it
                  before running.
                </p>
              </div>
              <Chip variant="outline">Novice flow</Chip>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={topicInput}
                onChange={(e) => setTopicInput(e.target.value)}
                placeholder="e.g. Prompt injection in enterprise copilots"
                className="flex-1 bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent"
              />
              <Button
                variant="default"
                size="sm"
                onClick={handleGenerateCluster}
                disabled={generatingCluster || topicInput.trim().length < 3}
              >
                {generatingCluster ? "Generating…" : "Generate subtopics"}
              </Button>
            </div>
            <p className="text-xs text-muted mt-2">
              This creates a stage-1 cluster draft (topic -> cluster -> subtopics with starter keywords).
            </p>
            {generationInfo && (
              <p className="text-xs text-accent mt-2">{generationInfo}</p>
            )}
            <div className="mt-3 pt-3 border-t border-border/60">
              <button
                type="button"
                onClick={() => {
                  setShowAdvanced((prev) => !prev);
                  if (!showAdvanced && !clusterJson) {
                    parseJson(JSON.stringify(EXAMPLE_CLUSTER, null, 2));
                  }
                }}
                className="text-xs text-accent hover:underline"
              >
                {showAdvanced ? "Hide advanced JSON editor" : "Show advanced JSON editor"}
              </button>
            </div>
          </Card>

          {showAdvanced && (
            <Card padding="lg">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-bold text-foreground">
                  Cluster Configuration
                </h2>
                <a
                  href="#"
                  className="text-xs text-accent hover:underline"
                  onClick={(e) => {
                    e.preventDefault();
                    parseJson(JSON.stringify(EXAMPLE_CLUSTER, null, 2));
                  }}
                >
                  Load example
                </a>
              </div>

              <Textarea
                label="Cluster JSON"
                id="cluster-json"
                rows={18}
                value={clusterJson}
                onChange={(e) => parseJson(e.target.value)}
                error={parseError ?? undefined}
                placeholder='{ "pillar": "...", "clusters": [...] }'
                className="font-mono text-xs"
              />

              {parsedCluster && !parseError && (
                <div className="mt-3 p-3 bg-green-500/5 border border-green-500/20 rounded-lg">
                  <p className="text-xs text-green-400 font-medium">
                    ✓ Valid — {parsedCluster.pillar} · {allSubtopics.length} subtopic
                    {allSubtopics.length !== 1 ? "s" : ""}
                  </p>
                </div>
              )}
            </Card>
          )}

          {/* Save cluster */}
          {showAdvanced && parsedCluster && !parseError && (
            <Card>
              <p className="text-sm text-muted mb-2">Save this cluster for reuse (optional)</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Cluster name, e.g. Prompt Injection 2026"
                  value={clusterName}
                  onChange={(e) => setClusterName(e.target.value)}
                  className="flex-1 bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent"
                />
                <Button
                  variant="default"
                  size="sm"
                  onClick={handleSaveCluster}
                  disabled={saving || !clusterName.trim()}
                >
                  {saving ? "Saving…" : "Save"}
                </Button>
              </div>
            </Card>
          )}
        </div>

        {/* ── Right: Subtopics + Sources + Filters ─────────────────── */}
        <div className="space-y-4">
          {/* Subtopic selection */}
          {parsedCluster && !parseError && allSubtopics.length > 0 && (
            <Card padding="lg">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-bold text-foreground">Subtopics</h2>
                <div className="flex gap-2">
                  <button
                    onClick={() =>
                      setSelectedSubtopics(new Set(allSubtopics.map((x) => x.subtopic.name)))
                    }
                    className="text-xs text-accent hover:underline"
                  >
                    All
                  </button>
                  <span className="text-muted text-xs">·</span>
                  <button
                    onClick={() => setSelectedSubtopics(new Set())}
                    className="text-xs text-muted hover:text-foreground"
                  >
                    None
                  </button>
                </div>
              </div>
              <div className="space-y-3">
                {parsedCluster.clusters.map((cluster) => (
                  <div key={cluster.name}>
                    <p className="text-xs text-muted uppercase tracking-wider mb-1.5">
                      {cluster.name}
                    </p>
                    <div className="space-y-1">
                      {cluster.subtopics.map((sub) => (
                        <label
                          key={sub.name}
                          className="flex items-start gap-3 cursor-pointer group"
                        >
                          <input
                            type="checkbox"
                            checked={selectedSubtopics.has(sub.name)}
                            onChange={() => toggleSubtopic(sub.name)}
                            className="mt-0.5 accent-accent"
                          />
                          <div>
                            <span className="text-sm text-foreground group-hover:text-accent transition-colors">
                              {sub.name}
                            </span>
                            <p className="text-xs text-muted mt-0.5">
                              {sub.keywords.slice(0, 4).join(", ")}
                              {sub.keywords.length > 4 && ` +${sub.keywords.length - 4} more`}
                            </p>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Source selection */}
          <Card padding="lg">
            <h2 className="text-base font-bold text-foreground mb-3">Sources</h2>
            <div className="space-y-2">
              {(Object.keys(SOURCE_LABELS) as (keyof SourceConfig)[]).map((key) => (
                <label key={key} className="flex items-start gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={sources[key]}
                    onChange={() => toggleSource(key)}
                    className="mt-0.5 accent-accent"
                  />
                  <div>
                    <span className="text-sm text-foreground group-hover:text-accent transition-colors font-medium">
                      {SOURCE_LABELS[key].label}
                    </span>
                    <p className="text-xs text-muted">{SOURCE_LABELS[key].hint}</p>
                  </div>
                </label>
              ))}
            </div>
            {!anySourceEnabled && (
              <p className="text-xs text-amber-400 mt-2">Select at least one source.</p>
            )}
          </Card>

          {/* Filters */}
          <Card padding="lg">
            <h2 className="text-base font-bold text-foreground mb-3">Filters</h2>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-muted block mb-1">
                  Minimum relevance gate: {minScore}%
                </label>
                <input
                  type="range"
                  min={0}
                  max={60}
                  step={5}
                  value={minScore}
                  onChange={(e) => setMinScore(Number(e.target.value))}
                  className="w-full accent-accent"
                />
                <div className="flex justify-between text-xs text-muted mt-1">
                  <span>0% (show all)</span>
                  <span>60% (strict)</span>
                </div>
                <p className="text-xs text-muted/70 mt-1">
                  Hard gate: results below this relevance score are excluded.
                  Default 0% = pipeline gate of 25% applies.
                </p>
              </div>
            </div>
          </Card>

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Run button */}
          <Button
            variant="primary"
            size="lg"
            className="w-full justify-center"
            disabled={!canRun || submitting}
            onClick={handleStartRun}
          >
            {submitting
              ? "Starting…"
              : !parsedCluster || parseError
                ? "Fix cluster JSON to continue"
                : !anySourceEnabled
                  ? "Enable at least one source"
                  : !anySubtopicSelected
                    ? "Select at least one subtopic"
                    : `Start Discovery → ${selectedSubtopics.size} subtopic${selectedSubtopics.size !== 1 ? "s" : ""}`}
          </Button>

          <p className="text-xs text-muted text-center">
            Each subtopic generates 2–3 queries per source API.
            Runs are scored and saved — no data is discarded.
          </p>
        </div>
      </div>
    </div>
  );
}
