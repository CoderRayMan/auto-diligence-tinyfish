/* Re-export types matching backend schemas */

export type ScanStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
export type Severity = "critical" | "high" | "medium" | "low";
export type FindingStatus = "open" | "settled" | "closed" | "appealed" | "unknown";

export interface ScanRequest {
  target: string;
  query?: string;
  sources?: string[];
  persona_id?: string;
  date_from?: string;
  date_to?: string;
  max_concurrent_agents?: number;
}

export interface SourceResult {
  source_id: string;
  status: string;
  records_found: number;
  execution_time_s: number;
  error?: string;
}

export interface Scan {
  scan_id: string;
  status: ScanStatus;
  target: string;
  query: string;
  persona_id?: string;
  created_at: string;
  completed_at?: string;
  sources_total: number;
  sources_completed: number;
  sources_failed: number;
  risk_score?: number;
  risk_label?: string;
  findings_count: number;
  source_results: SourceResult[];
}

export interface Finding {
  finding_id: string;
  scan_id: string;
  source_id: string;
  case_id: string;
  case_type: string;
  entity_name: string;
  violation_type: string;
  decision_date: string;
  penalty_amount: number;
  severity: Severity;
  status: FindingStatus;
  description: string;
  source_url: string;
  jurisdiction: string;
}

export interface FindingsPage {
  scan_id: string;
  total: number;
  page: number;
  page_size: number;
  findings: Finding[];
}

export interface AgentEvent {
  scan_id: string;
  source_id: string;
  agent_tag: "RUNNING" | "COMPLETED" | "WAITING" | "FAILED" | "STREAMING_URL";
  message: string;
  timestamp: string;
  streaming_url?: string; // Live TinyFish browser stream URL
}

// ── Persona types ─────────────────────────────────────────

export interface DemoTarget {
  name: string;
  description: string;
  query_override?: string;
}

export interface Persona {
  id: string;
  label: string;
  icon: string;
  description: string;
  color: string;
  default_sources: string[];
  default_query: string;
  focus_areas: string[];
  demo_targets: DemoTarget[];
}

// ── Watchlist types ───────────────────────────────────────

export interface WatchlistEntry {
  entity_name: string;
  added_at: string;
  last_scan_id?: string;
  last_scan_at?: string;
  last_risk_score?: number;
  last_risk_label?: string;
  is_stale: boolean;
  persona_id?: string;
  notes?: string;
}

// ── Analytics types ───────────────────────────────────────

export interface RiskTrendPoint {
  scan_id: string;
  date: string;
  risk_score?: number;
  risk_label?: string;
  findings_count: number;
  sources_queried: number;
}

export interface RiskTrend {
  target: string;
  total_scans: number;
  shown: number;
  trend: "improving" | "worsening" | "stable";
  delta_risk: number;
  current_risk_score?: number;
  data_points: RiskTrendPoint[];
}

export interface PortfolioOverview {
  total_scans: number;
  total_findings: number;
  total_exposure: number;
  avg_risk_score?: number;
  entities_at_risk: Array<{
    target: string;
    scan_id: string;
    risk_score?: number;
    risk_label?: string;
    findings_count: number;
    last_scanned: string;
  }>;
  by_severity: Record<string, number>;
  by_source: Record<string, number>;
}

// ── Toast notification ────────────────────────────────────

export type ToastLevel = "info" | "success" | "warning" | "error";

export interface Toast {
  id: string;
  message: string;
  level: ToastLevel;
}

// ── Scheduler types ───────────────────────────────────────

export interface SchedulerStatus {
  running: boolean;
  paused: boolean;
  interval_minutes: number;
  last_sweep_at?: string;
  next_sweep_at?: string;
  sweep_count: number;
  recent_sweeps: Array<{
    swept_at: string;
    entities_queued: number;
    scan_ids: string[];
    triggered_manually?: boolean;
  }>;
}

// ── TinyFish Run Audit types ──────────────────────────────

export interface RunSummary {
  run_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  goal_preview: string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  duration_seconds?: number;
  streaming_url?: string;
  has_result: boolean;
  error_message?: string;
}

export interface RunDetail extends RunSummary {
  goal: string;
  result?: Record<string, unknown>;
  error_category?: string;
  proxy_enabled?: boolean;
  proxy_country?: string;
}

export interface RunListResponse {
  runs: RunSummary[];
  total: number;
  has_more: boolean;
  next_cursor?: string;
}

export interface RunStats {
  total_runs: number;
  completed: number;
  failed: number;
  pending_or_running: number;
  success_rate_pct: number;
  avg_duration_seconds?: number;
  total_goals_fired: number;
}

// ── AI Digest types ───────────────────────────────────────

export interface DigestResponse {
  digest_type: string;
  target?: string;
  generated_at: string;
  briefing?: string;
  raw_result?: Record<string, unknown>;
  num_steps: number;
  duration_seconds?: number;
  run_id?: string;
  streaming_url?: string;
}

export interface QueuedEnrichmentResponse {
  message: string;
  queued_run_ids: string[];
  targets_queued: string[];
}

