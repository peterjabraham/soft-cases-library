"use client";

import type {
  ClusterConfig,
  FilterConfig,
  QueryJob,
  ResultFilters,
  Run,
  SavedCluster,
  GeneratedClusterResponse,
  ScoredResult,
  SourceConfig,
} from "./types";

function getBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8004";
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sc_token");
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    const msg =
      err?.detail?.error?.message || err?.detail || err?.message || `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return res.json() as Promise<T>;
}

// ── Clusters ──────────────────────────────────────────────────────────────────

export async function listClusters(): Promise<SavedCluster[]> {
  const res = await fetch(`${getBaseUrl()}/api/v1/clusters`, {
    headers: authHeaders(),
  });
  return handleResponse<SavedCluster[]>(res);
}

export async function saveCluster(
  name: string,
  cluster_config: ClusterConfig,
): Promise<SavedCluster> {
  const res = await fetch(`${getBaseUrl()}/api/v1/clusters`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ name, cluster_config }),
  });
  return handleResponse<SavedCluster>(res);
}

export async function generateClusterFromTopic(
  topic: string,
): Promise<GeneratedClusterResponse> {
  const res = await fetch(`${getBaseUrl()}/api/v1/clusters/generate`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ topic }),
  });
  return handleResponse<GeneratedClusterResponse>(res);
}

// ── Runs ──────────────────────────────────────────────────────────────────────

export async function createRun(
  cluster_config: ClusterConfig,
  source_config: SourceConfig,
  cluster_id?: string,
  filter_config?: FilterConfig,
): Promise<Run> {
  const res = await fetch(`${getBaseUrl()}/api/v1/runs`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ cluster_config, source_config, cluster_id, filter_config }),
  });
  return handleResponse<Run>(res);
}

export async function getRun(runId: string): Promise<Run> {
  const res = await fetch(`${getBaseUrl()}/api/v1/runs/${runId}`, {
    headers: authHeaders(),
  });
  return handleResponse<Run>(res);
}

export async function startRun(runId: string): Promise<Run> {
  const res = await fetch(`${getBaseUrl()}/api/v1/runs/${runId}/start`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<Run>(res);
}

export async function getRunJobs(runId: string): Promise<QueryJob[]> {
  const res = await fetch(`${getBaseUrl()}/api/v1/runs/${runId}/jobs`, {
    headers: authHeaders(),
  });
  return handleResponse<QueryJob[]>(res);
}

// ── Results ───────────────────────────────────────────────────────────────────

export async function getResults(
  runId: string,
  filters: Partial<ResultFilters>,
): Promise<ScoredResult[]> {
  const params = new URLSearchParams();
  if (filters.content_type) params.set("content_type", filters.content_type);
  if (filters.min_score !== undefined) params.set("min_score", String(filters.min_score));
  if (filters.source_tier) params.set("source_tier", filters.source_tier);
  if (filters.subtopic) params.set("subtopic", filters.subtopic);
  if (filters.sort) params.set("sort", filters.sort);
  if (filters.order) params.set("order", filters.order);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.per_page) params.set("per_page", String(filters.per_page));

  const res = await fetch(
    `${getBaseUrl()}/api/v1/runs/${runId}/results?${params.toString()}`,
    { headers: authHeaders() },
  );
  return handleResponse<ScoredResult[]>(res);
}

export function exportCsvUrl(runId: string): string {
  return `${getBaseUrl()}/api/v1/runs/${runId}/export/csv`;
}

export function exportJsonUrl(runId: string): string {
  return `${getBaseUrl()}/api/v1/runs/${runId}/export/json`;
}
