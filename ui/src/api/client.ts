import type {
  Scan,
  ScanRequest,
  FindingsPage,
  AgentEvent,
  Persona,
  WatchlistEntry,
  RiskTrend,
  PortfolioOverview,
  SchedulerStatus,
  RunListResponse,
  RunDetail,
  RunStats,
  DigestResponse,
  QueuedEnrichmentResponse,
} from "./types";

const BASE = (process.env.REACT_APP_API_URL ?? "").replace(/\/$/, "") + "/api";

async function _json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`[${res.status}] ${text}`);
  }
  return res.json() as Promise<T>;
}

// ------------------------------------------------------------------ scans

export async function createScan(req: ScanRequest): Promise<Scan> {
  const res = await fetch(`${BASE}/scans`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return _json<Scan>(res);
}

export async function getScan(scanId: string): Promise<Scan> {
  const res = await fetch(`${BASE}/scans/${scanId}`);
  return _json<Scan>(res);
}

export async function listScans(): Promise<Scan[]> {
  const res = await fetch(`${BASE}/scans`);
  return _json<Scan[]>(res);
}

export async function cancelScan(scanId: string): Promise<void> {
  await fetch(`${BASE}/scans/${scanId}`, { method: "DELETE" });
}

// --------------------------------------------------------------- findings

export async function getFindings(
  scanId: string,
  opts: {
    severity?: string;
    status?: string;
    source_id?: string;
    page?: number;
    page_size?: number;
  } = {}
): Promise<FindingsPage> {
  const params = new URLSearchParams({ scan_id: scanId });
  if (opts.severity)  params.set("severity", opts.severity);
  if (opts.status)    params.set("status", opts.status);
  if (opts.source_id) params.set("source_id", opts.source_id);
  if (opts.page)      params.set("page", String(opts.page));
  if (opts.page_size) params.set("page_size", String(opts.page_size));

  const res = await fetch(`${BASE}/findings?${params}`);
  return _json<FindingsPage>(res);
}

// ---------------------------------------------------------- SSE / agents

/**
 * Fetch the full event history for a scan (emitted before SSE connection opened).
 */
export async function getAgentEventHistory(scanId: string): Promise<AgentEvent[]> {
  const res = await fetch(`${BASE}/agents/events?scan_id=${encodeURIComponent(scanId)}`);
  if (!res.ok) return [];
  const data = await res.json() as { events: AgentEvent[] };
  return data.events ?? [];
}

/**
 * Open an SSE connection for live agent events.
 * Returns a cleanup function to close the connection.
 */
export function subscribeAgentEvents(
  scanId: string,
  onEvent: (event: AgentEvent) => void,
  onDone: () => void,
  onError?: (err: Event) => void
): () => void {
  const url = `${BASE}/agents/stream?scan_id=${encodeURIComponent(scanId)}`;
  const es = new EventSource(url);

  es.addEventListener("agent_event", (e: MessageEvent) => {
    try {
      onEvent(JSON.parse(e.data) as AgentEvent);
    } catch {
      /* ignore malformed events */
    }
  });

  es.addEventListener("done", () => {
    es.close();
    onDone();
  });

  if (onError) {
    es.onerror = onError;
  }

  return () => es.close();
}

export async function getAgentStatus(scanId: string) {
  const res = await fetch(`${BASE}/agents/status?scan_id=${scanId}`);
  return _json<Record<string, unknown>>(res);
}

// --------------------------------------------------------------- personas

export async function listPersonas(): Promise<Persona[]> {
  const res = await fetch(`${BASE}/personas`);
  return _json<Persona[]>(res);
}

// --------------------------------------------------------- findings extras

/**
 * Download findings as CSV.  Opens a download link in the browser.
 */
export function downloadFindingsCSV(scanId: string): void {
  const url = `${BASE}/findings/export/csv?scan_id=${encodeURIComponent(scanId)}`;
  const a = document.createElement("a");
  a.href = url;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/**
 * Fetch aggregate stats / executive summary for a scan.
 */
export async function getFindingsStats(scanId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/findings/stats/summary?scan_id=${encodeURIComponent(scanId)}`);
  return _json<Record<string, unknown>>(res);
}

/**
 * Re-run a previous scan with the same parameters.
 */
export async function rerunScan(scanId: string): Promise<Scan> {
  const res = await fetch(`${BASE}/scans/${scanId}/rerun`, { method: "POST" });
  return _json<Scan>(res);
}

/**
 * Fetch the structured executive report for a completed scan.
 */
export async function getExecutiveReport(scanId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/findings/report/executive?scan_id=${encodeURIComponent(scanId)}`);
  return _json<Record<string, unknown>>(res);
}

/**
 * Compare two scans side-by-side.
 */
export async function compareScans(scanA: string, scanB: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/findings/compare?scan_a=${encodeURIComponent(scanA)}&scan_b=${encodeURIComponent(scanB)}`);
  return _json<Record<string, unknown>>(res);
}

// ----------------------------------------------------------------- watchlist

export async function listWatchlist(): Promise<WatchlistEntry[]> {
  const res = await fetch(`${BASE}/watchlist`);
  return _json<WatchlistEntry[]>(res);
}

export async function addToWatchlist(entityName: string, personaId?: string, notes?: string): Promise<WatchlistEntry> {
  const res = await fetch(`${BASE}/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_name: entityName, persona_id: personaId, notes }),
  });
  return _json<WatchlistEntry>(res);
}

export async function removeFromWatchlist(entityName: string): Promise<void> {
  await fetch(`${BASE}/watchlist/${encodeURIComponent(entityName)}`, { method: "DELETE" });
}

export async function getStaleWatchlist(): Promise<WatchlistEntry[]> {
  const res = await fetch(`${BASE}/watchlist/stale`);
  return _json<WatchlistEntry[]>(res);
}

// ----------------------------------------------------------------- analytics

export async function getRiskTrend(target: string, limit = 10): Promise<RiskTrend> {
  const res = await fetch(`${BASE}/analytics/risk-trend?target=${encodeURIComponent(target)}&limit=${limit}`);
  return _json<RiskTrend>(res);
}

export async function searchFindings(
  q: string,
  opts: { scan_id?: string; severity?: string; limit?: number } = {}
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams({ q });
  if (opts.scan_id)  params.set("scan_id", opts.scan_id);
  if (opts.severity) params.set("severity", opts.severity);
  if (opts.limit)    params.set("limit", String(opts.limit));
  const res = await fetch(`${BASE}/analytics/search?${params}`);
  return _json<Record<string, unknown>>(res);
}

export async function getPortfolioOverview(): Promise<PortfolioOverview> {
  const res = await fetch(`${BASE}/analytics/portfolio`);
  return _json<PortfolioOverview>(res);
}

export async function getBenchmark(target: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/analytics/benchmark?target=${encodeURIComponent(target)}`);
  return _json<Record<string, unknown>>(res);
}

// ----------------------------------------------------------------- health

export async function getHealth(): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/health`);
  return _json<Record<string, unknown>>(res);
}

// ----------------------------------------------------------------- scheduler

export async function getSchedulerStatus(): Promise<SchedulerStatus> {
  const res = await fetch(`${BASE}/scheduler/status`);
  return _json<SchedulerStatus>(res);
}

export async function triggerSchedulerSweep(): Promise<{ message: string; scan_ids: string[] }> {
  const res = await fetch(`${BASE}/scheduler/trigger`, { method: "POST" });
  return _json(res);
}

export async function pauseScheduler(): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/scheduler/pause`, { method: "POST" });
  return _json(res);
}

export async function resumeScheduler(): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/scheduler/resume`, { method: "POST" });
  return _json(res);
}

export async function startScheduler(): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/scheduler/start`, { method: "POST" });
  return _json(res);
}

// ----------------------------------------------------------------- TinyFish run audit

export async function listRuns(opts: {
  status?: string;
  goal?: string;
  limit?: number;
  cursor?: string;
} = {}): Promise<RunListResponse> {
  const params = new URLSearchParams();
  if (opts.status) params.set("status", opts.status);
  if (opts.goal)   params.set("goal", opts.goal);
  if (opts.limit)  params.set("limit", String(opts.limit));
  if (opts.cursor) params.set("cursor", opts.cursor);
  const res = await fetch(`${BASE}/runs?${params}`);
  return _json<RunListResponse>(res);
}

export async function getRun(runId: string): Promise<RunDetail> {
  const res = await fetch(`${BASE}/runs/${encodeURIComponent(runId)}`);
  return _json<RunDetail>(res);
}

export async function getRunStats(limit = 100): Promise<RunStats> {
  const res = await fetch(`${BASE}/runs/stats?limit=${limit}`);
  return _json<RunStats>(res);
}

// ----------------------------------------------------------------- AI digest

export async function generatePortfolioDigest(): Promise<DigestResponse> {
  const res = await fetch(`${BASE}/digest/portfolio`, { method: "POST" });
  return _json<DigestResponse>(res);
}

export async function generateEntityDigest(target: string): Promise<DigestResponse> {
  const res = await fetch(`${BASE}/digest/entity?target=${encodeURIComponent(target)}`, { method: "POST" });
  return _json<DigestResponse>(res);
}

export async function generateRiskSpikeDigest(target: string): Promise<DigestResponse> {
  const res = await fetch(`${BASE}/digest/risk-spike?target=${encodeURIComponent(target)}`, { method: "POST" });
  return _json<DigestResponse>(res);
}

export async function queueBatchEnrichment(targets: string[]): Promise<QueuedEnrichmentResponse> {
  const res = await fetch(
    `${BASE}/digest/queue-enrichment?targets=${encodeURIComponent(targets.join(","))}`,
    { method: "POST" }
  );
  return _json<QueuedEnrichmentResponse>(res);
}

export async function geoScan(target: string, countryCode: string): Promise<DigestResponse> {
  const res = await fetch(
    `${BASE}/digest/geo-scan?target=${encodeURIComponent(target)}&country_code=${countryCode}`,
    { method: "POST" }
  );
  return _json<DigestResponse>(res);
}
