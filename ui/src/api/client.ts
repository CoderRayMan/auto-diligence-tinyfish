import type {
  Scan,
  ScanRequest,
  FindingsPage,
  AgentEvent,
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
