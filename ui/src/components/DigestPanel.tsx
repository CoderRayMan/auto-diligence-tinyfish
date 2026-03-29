import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Bot,
  Building2,
  Globe,
  Info,
  Loader2,
  TrendingUp,
  Zap,
} from "lucide-react";
import {
  generatePortfolioDigest,
  generateEntityDigest,
  generateRiskSpikeDigest,
  getRun,
  queueBatchEnrichment,
  geoScan,
} from "../api/client";
import type { DigestResponse, RunDetail } from "../api/types";
import "./DigestPanel.css";

type DigestTab = "portfolio" | "entity" | "spike" | "geo" | "batch";

type PendingDigestRun = {
  runId: string;
  digestType: string;
  target?: string;
  activeTab: Exclude<DigestTab, "batch">;
  generatedAt: string;
};

type DigestPanelSnapshot = {
  result?: DigestResponse | null;
  pendingRun?: PendingDigestRun | null;
  batchResult?: { message: string; queued_run_ids: string[] } | null;
};

const DIGEST_STORAGE_KEY = "autodiligence.digestPanel";
const DIGEST_POLL_INTERVAL_MS = 5000;

function readDigestSnapshot(): DigestPanelSnapshot {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const raw = window.sessionStorage.getItem(DIGEST_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as DigestPanelSnapshot) : {};
  } catch {
    return {};
  }
}

function writeDigestSnapshot(snapshot: DigestPanelSnapshot): void {
  if (typeof window === "undefined") {
    return;
  }

  if (!snapshot.result && !snapshot.pendingRun && !snapshot.batchResult) {
    window.sessionStorage.removeItem(DIGEST_STORAGE_KEY);
    return;
  }

  window.sessionStorage.setItem(DIGEST_STORAGE_KEY, JSON.stringify(snapshot));
}

function inferDigestTab(snapshot: DigestPanelSnapshot): DigestTab {
  if (snapshot.pendingRun) {
    return snapshot.pendingRun.activeTab;
  }

  const digestType = snapshot.result?.digest_type;
  if (digestType === "portfolio") {
    return "portfolio";
  }
  if (digestType === "entity") {
    return "entity";
  }
  if (digestType === "risk_spike") {
    return "spike";
  }
  if (digestType?.startsWith("geo_scan_")) {
    return "geo";
  }

  return "portfolio";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isQueuedDigest(response: DigestResponse): boolean {
  return Boolean(
    response.run_id &&
    (response.raw_result as Record<string, unknown> | undefined)?.mode === "queued"
  );
}

function materializeDigestResponse(base: PendingDigestRun, run: RunDetail): DigestResponse {
  const rawResult = run.result ?? {};
  return {
    digest_type: base.digestType,
    target: base.target,
    generated_at: run.finished_at ?? run.created_at ?? base.generatedAt,
    briefing: typeof rawResult.briefing === "string" ? rawResult.briefing : undefined,
    raw_result: rawResult,
    num_steps: 0,
    duration_seconds: run.duration_seconds,
    run_id: run.run_id,
    streaming_url: run.streaming_url,
  };
}

const GEO_OPTIONS = [
  { code: "US", label: "US (SEC)" },
  { code: "GB", label: "UK (FCA)" },
  { code: "CA", label: "Canada (OSC)" },
  { code: "DE", label: "Germany (BaFin)" },
  { code: "FR", label: "France (AMF)" },
  { code: "JP", label: "Japan (FSA)" },
  { code: "AU", label: "Australia (ASIC)" },
];

export const DigestPanel: React.FC<{ scannedTargets: string[] }> = ({ scannedTargets }) => {
  const snapshot = readDigestSnapshot();
  const [activeTab, setActiveTab] = useState<DigestTab>(inferDigestTab(snapshot));
  const [result, setResult] = useState<DigestResponse | null>(snapshot.result ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingRun, setPendingRun] = useState<PendingDigestRun | null>(snapshot.pendingRun ?? null);
  const [pendingStatus, setPendingStatus] = useState<string | null>(snapshot.pendingRun ? "RUNNING" : null);

  // Entity / spike state
  const [entityTarget, setEntityTarget] = useState(scannedTargets[0] || "");
  const [spikeTarget, setSpikeTarget] = useState(scannedTargets[0] || "");

  // Geo state
  const [geoTarget, setGeoTarget] = useState(scannedTargets[0] || "");
  const [geoCountry, setGeoCountry] = useState("US");

  // Batch state
  const [batchTargets, setBatchTargets] = useState(scannedTargets.slice(0, 3).join(", "));
  const [batchResult, setBatchResult] = useState<{ message: string; queued_run_ids: string[] } | null>(snapshot.batchResult ?? null);

  const busy = loading || pendingRun !== null;

  useEffect(() => {
    writeDigestSnapshot({ result, pendingRun, batchResult });
  }, [result, pendingRun, batchResult]);

  useEffect(() => {
    if (!pendingRun) {
      setPendingStatus(null);
      return;
    }

    let cancelled = false;

    const poll = async () => {
      while (!cancelled) {
        try {
          const run = await getRun(pendingRun.runId);
          if (cancelled) {
            return;
          }

          setPendingStatus(run.status);

          if (run.status === "COMPLETED") {
            const completedDigest = materializeDigestResponse(pendingRun, run);
            writeDigestSnapshot({
              result: completedDigest,
              pendingRun: null,
              batchResult,
            });
            setActiveTab(pendingRun.activeTab);
            setResult(completedDigest);
            setPendingRun(null);
            setError(null);
            return;
          }

          if (run.status === "FAILED" || run.status === "CANCELLED") {
            writeDigestSnapshot({
              result: null,
              pendingRun: null,
              batchResult,
            });
            setError(run.error_message || `TinyFish run ${run.status.toLowerCase()}.`);
            setPendingRun(null);
            return;
          }
        } catch (e: unknown) {
          if (!cancelled) {
            writeDigestSnapshot({
              result: null,
              pendingRun: null,
              batchResult,
            });
            setError(e instanceof Error ? e.message : String(e));
            setPendingRun(null);
          }
          return;
        }

        await sleep(DIGEST_POLL_INTERVAL_MS);
      }
    };

    void poll();

    return () => {
      cancelled = true;
    };
  }, [pendingRun, batchResult]);

  const run = async (
    tab: Exclude<DigestTab, "batch">,
    fn: () => Promise<DigestResponse>,
  ) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setPendingRun(null);
    setPendingStatus(null);
    try {
      const r = await fn();

      if (isQueuedDigest(r) && r.run_id) {
        const nextPendingRun = {
          runId: r.run_id,
          digestType: r.digest_type,
          target: r.target,
          activeTab: tab,
          generatedAt: r.generated_at,
        };
        writeDigestSnapshot({
          result: null,
          pendingRun: nextPendingRun,
          batchResult: null,
        });
        setPendingRun(nextPendingRun);
        setActiveTab(tab);
      } else {
        writeDigestSnapshot({
          result: r,
          pendingRun: null,
          batchResult: null,
        });
        setActiveTab(tab);
        setResult(r);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleBatchQueue = async () => {
    setLoading(true);
    setError(null);
    setBatchResult(null);
    try {
      const targets = batchTargets.split(",").map(t => t.trim()).filter(Boolean);
      const r = await queueBatchEnrichment(targets);
      setBatchResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
    setLoading(false);
  };

  return (
    <div className="digest-panel">
      <div className="digest-header">
        <h3><Bot size={16} aria-hidden /> AI Intelligence Briefings</h3>
        <p className="digest-subtitle">
          Powered by <strong>TinyFish agent.queue()</strong> with live run polling and structured output
        </p>
      </div>

      {/* Tabs */}
      <div className="digest-tabs">
        {[
          { id: "portfolio", label: "Portfolio Brief", Icon: BarChart3 },
          { id: "entity",    label: "Entity Deep-Dive", Icon: Building2 },
          { id: "spike",     label: "Risk Spike Explain", Icon: TrendingUp },
          { id: "geo",       label: "Geo-Targeted Scan", Icon: Globe },
          { id: "batch",     label: "Batch Queue", Icon: Zap },
        ].map(tab => (
          <button
            key={tab.id}
            className={`digest-tab ${activeTab === tab.id ? "digest-tab--active" : ""}`}
            onClick={() => { setActiveTab(tab.id as DigestTab); setResult(null); setError(null); }}
          >
            <tab.Icon size={13} aria-hidden /> {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="digest-body">
        {/* Portfolio briefing */}
        {activeTab === "portfolio" && (
          <div className="digest-form">
            <p className="digest-desc">
              Queues a live Reuters Legal research run and keeps polling the TinyFish audit API until the
              completed briefing is ready. You can leave and return to this panel while it runs.
            </p>
            <button
              className="digest-run-btn"
              onClick={() => run("portfolio", generatePortfolioDigest)}
              disabled={busy}
            >
              {busy ? <><Loader2 size={13} /> Generating...</> : <><BarChart3 size={13} /> Generate Portfolio Briefing</>}
            </button>
          </div>
        )}

        {/* Entity deep-dive */}
        {activeTab === "entity" && (
          <div className="digest-form">
            <p className="digest-desc">
              Queues a live SEC EDGAR research run and hydrates the final narrative as soon as the TinyFish
              run completes.
            </p>
            <div className="digest-input-row">
              <select
                value={entityTarget}
                onChange={e => setEntityTarget(e.target.value)}
                className="digest-select"
              >
                {scannedTargets.map(t => <option key={t}>{t}</option>)}
              </select>
              <button
                className="digest-run-btn"
                onClick={() => run("entity", () => generateEntityDigest(entityTarget))}
                disabled={busy || !entityTarget}
              >
                {busy ? <><Loader2 size={13} /> Researching...</> : <><Building2 size={13} /> Generate Entity Brief</>}
              </button>
            </div>
          </div>
        )}

        {/* Risk spike */}
        {activeTab === "spike" && (
          <div className="digest-form">
            <p className="digest-desc">
              Queues a Reuters research run to explain why a risk score changed between two scans, then
              restores the explanation once the run is completed.
            </p>
            <div className="digest-input-row">
              <select
                value={spikeTarget}
                onChange={e => setSpikeTarget(e.target.value)}
                className="digest-select"
              >
                {scannedTargets.map(t => <option key={t}>{t}</option>)}
              </select>
              <button
                className="digest-run-btn"
                onClick={() => run("spike", () => generateRiskSpikeDigest(spikeTarget))}
                disabled={busy || !spikeTarget}
              >
                {busy ? <><Loader2 size={13} /> Analysing...</> : <><TrendingUp size={13} /> Explain Risk Spike</>}
              </button>
            </div>
          </div>
        )}

        {/* Geo-targeted scan */}
        {activeTab === "geo" && (
          <div className="digest-form">
            <p className="digest-desc">
              Queues a geo-routed TinyFish run with <code>ProxyConfig(country_code=...)</code> and waits for
              the jurisdiction-specific research result to complete.
            </p>
            <div className="digest-input-row">
              <select value={geoTarget} onChange={e => setGeoTarget(e.target.value)} className="digest-select">
                {scannedTargets.map(t => <option key={t}>{t}</option>)}
              </select>
              <select value={geoCountry} onChange={e => setGeoCountry(e.target.value)} className="digest-select">
                {GEO_OPTIONS.map(g => (
                  <option key={g.code} value={g.code}>{g.label}</option>
                ))}
              </select>
              <button
                className="digest-run-btn"
                onClick={() => run("geo", () => geoScan(geoTarget, geoCountry))}
                disabled={busy || !geoTarget}
              >
                {busy ? <><Loader2 size={13} /> Scanning...</> : <><Globe size={13} /> Run Geo-Scan</>}
              </button>
            </div>
            <div className="digest-geo-note">
              <Info size={13} aria-hidden /> Browser will exit from <strong>{GEO_OPTIONS.find(g => g.code === geoCountry)?.label}</strong>
            </div>
          </div>
        )}

        {/* Batch queue */}
        {activeTab === "batch" && (
          <div className="digest-form">
            <p className="digest-desc">
              Uses <code>agent.queue()</code> to fire-and-forget enrichment runs for multiple entities.
              Non-blocking — returns TinyFish <strong>run_ids</strong> immediately so you can poll
              <code>/api/runs/&#123;run_id&#125;</code> for results.
            </p>
            <textarea
              className="digest-batch-input"
              value={batchTargets}
              onChange={e => setBatchTargets(e.target.value)}
              placeholder="Tesla, Boeing, Apple (comma-separated)"
              rows={3}
            />
            <button
              className="digest-run-btn"
              onClick={handleBatchQueue}
              disabled={busy}
            >
              {busy ? <><Loader2 size={13} /> Queuing...</> : <><Zap size={13} /> Queue Batch Enrichment</>}
            </button>
            {batchResult && (
              <div className="digest-batch-result">
                <div className="digest-batch-msg">{batchResult.message}</div>
                <div className="digest-batch-ids">
                  {batchResult.queued_run_ids.map(id => (
                    <code key={id} className="digest-run-id">{id}</code>
                  ))}
                </div>
                {batchResult.queued_run_ids.length === 0 && (
                  <div className="digest-no-runs">No runs queued — check TinyFish API key</div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="digest-error">
            <AlertTriangle size={13} aria-hidden /> {error}
          </div>
        )}

        {pendingRun && (
          <div className="digest-progress-card" role="status" aria-live="polite">
            <div className="digest-progress-title">
              <Loader2 size={14} aria-hidden /> Live TinyFish research in progress
            </div>
            <p className="digest-progress-copy">
              This briefing is running in TinyFish now. You can switch tabs or open Run Audit; this panel will
              resume polling automatically when you come back.
            </p>
            <div className="digest-progress-meta">
              <span className="digest-progress-badge">{pendingStatus ?? "RUNNING"}</span>
              <code className="digest-run-id-small">{pendingRun.runId}</code>
            </div>
          </div>
        )}

        {/* Result card */}
        {result && activeTab !== "batch" && (
          <div className="digest-result-card">
            <div className="digest-result-meta">
              <span className="digest-type-badge">{result.digest_type.replace(/_/g, " ")}</span>
              {result.target && <span className="digest-result-target">· {result.target}</span>}
              <span className="digest-result-stats">
                {result.num_steps > 0 && <span>{result.num_steps} steps</span>}
                {typeof result.duration_seconds === "number" && (
                  <span>{result.num_steps > 0 ? " · " : ""}{result.duration_seconds.toFixed(0)}s</span>
                )}
                {result.run_id && <span>{result.num_steps > 0 || typeof result.duration_seconds === "number" ? " · " : ""}<code className="digest-run-id-small">{result.run_id.slice(0, 12)}…</code></span>}
              </span>
            </div>

            {result.briefing && (
              <div className="digest-briefing">
                {result.briefing}
              </div>
            )}

            {result.raw_result && !result.briefing && (
              <pre className="digest-raw-json">
                {JSON.stringify(result.raw_result, null, 2)}
              </pre>
            )}

            {Array.isArray((result.raw_result as Record<string,unknown>)?.key_risks) && (
              <div className="digest-risks">
                <div className="digest-section-label">Key Risks</div>
                <ul>
                  {((result.raw_result as Record<string,unknown[]>).key_risks).map((r, i) => (
                    <li key={i}>{String(r)}</li>
                  ))}
                </ul>
              </div>
            )}

            {Array.isArray((result.raw_result as Record<string,unknown>)?.recommended_actions) && (
              <div className="digest-actions">
                <div className="digest-section-label">Recommended Actions</div>
                <ul>
                  {((result.raw_result as Record<string,unknown[]>).recommended_actions).map((a, i) => (
                    <li key={i}>{String(a)}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DigestPanel;
