import type {
  Scan,
  ScanRequest,
  FindingsPage,
  AgentEvent,
  Persona,
} from "./types";

const BASE = "/api";

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
