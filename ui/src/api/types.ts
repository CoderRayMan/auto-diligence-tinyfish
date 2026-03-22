/* Re-export types matching backend schemas */

export type ScanStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
export type Severity = "critical" | "high" | "medium" | "low";
export type FindingStatus = "open" | "settled" | "closed" | "appealed" | "unknown";

export interface ScanRequest {
  target: string;
  query?: string;
  sources?: string[];
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
