// ── Cluster types ────────────────────────────────────────────────────────────

export interface Subtopic {
  name: string;
  keywords: string[];
}

export interface Cluster {
  name: string;
  subtopics: Subtopic[];
}

export interface ClusterConfig {
  pillar: string;
  clusters: Cluster[];
}

export interface SavedCluster {
  id: string;
  name: string;
  cluster_config: ClusterConfig;
  created_at: string;
}

// ── Run types ────────────────────────────────────────────────────────────────

export type RunStatus =
  | "queued"
  | "synthesising"
  | "discovering"
  | "deduplicating"
  | "scoring"
  | "complete"
  | "failed";

export interface Run {
  id: string;
  status: RunStatus;
  cluster_config: ClusterConfig;
  source_config: SourceConfig;
  filter_config: FilterConfig | null;
  total_discovered: number | null;
  total_deduped: number | null;
  total_scored: number | null;
  subtopic_relevance_scores: Record<string, number> | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface QueryJob {
  id: string;
  subtopic: string;
  source_api: "perplexity" | "semantic_scholar" | "arxiv";
  status: "queued" | "running" | "complete" | "failed";
  items_returned: number | null;
  error_message: string | null;
  retries: number;
}

// ── Source / filter config ────────────────────────────────────────────────────

export interface SourceConfig {
  perplexity: boolean;
  semantic_scholar: boolean;
  arxiv: boolean;
}

export interface FilterConfig {
  date_from?: string;
  date_to?: string;
  min_topical_relevance?: number;
  content_types?: string[];
}

// ── Scored result ─────────────────────────────────────────────────────────────

export interface ScoredResult {
  id: string;
  run_id: string;
  content_type: "academic" | "news" | "blog" | "unknown";
  url: string | null;
  doi: string | null;
  arxiv_id: string | null;
  title: string | null;
  authors: string[] | null;
  abstract_or_snippet: string | null;
  published_date: string | null;
  venue: string | null;
  source_tier: number | null;
  tier_multiplier: number | null;
  pillar: string | null;
  cluster_name: string | null;
  subtopic: string | null;
  matched_keywords: string[] | null;
  keyword_density: number | null;
  topical_relevance: number | null;
  citation_count: number | null;
  citation_velocity: number | null;
  influential_citations: number | null;
  venue_tier: number | null;
  arxiv_categories: string[] | null;
  is_preprint: boolean;
  category_tier: number | null;
  raw_score: number | null;
  final_score: number | null;
  score_confidence: number | null;
  excluded: boolean;
  excluded_reason: string | null;
  discovered_by: string[] | null;
  created_at: string;
}

// ── Result filter params ──────────────────────────────────────────────────────

export interface ResultFilters {
  content_type?: string;
  min_score?: number;
  source_tier?: string;
  subtopic?: string;
  sort: "final_score" | "citation_count" | "published_date" | "topical_relevance";
  order: "asc" | "desc";
  page: number;
  per_page: number;
}
