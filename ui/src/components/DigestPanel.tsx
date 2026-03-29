import React, { useState } from "react";
import {
  generatePortfolioDigest,
  generateEntityDigest,
  generateRiskSpikeDigest,
  queueBatchEnrichment,
  geoScan,
} from "../api/client";
import type { DigestResponse } from "../api/types";
import "./DigestPanel.css";

const GEO_OPTIONS = [
  { code: "US", label: "🇺🇸 US (SEC)" },
  { code: "GB", label: "🇬🇧 UK (FCA)" },
  { code: "CA", label: "🇨🇦 Canada (OSC)" },
  { code: "DE", label: "🇩🇪 Germany (BaFin)" },
  { code: "FR", label: "🇫🇷 France (AMF)" },
  { code: "JP", label: "🇯🇵 Japan (FSA)" },
  { code: "AU", label: "🇦🇺 Australia (ASIC)" },
];

export const DigestPanel: React.FC<{ scannedTargets: string[] }> = ({ scannedTargets }) => {
  const [activeTab, setActiveTab] = useState<"portfolio" | "entity" | "spike" | "geo" | "batch">("portfolio");
  const [result, setResult] = useState<DigestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Entity / spike state
  const [entityTarget, setEntityTarget] = useState(scannedTargets[0] || "");
  const [spikeTarget, setSpikeTarget] = useState(scannedTargets[0] || "");

  // Geo state
  const [geoTarget, setGeoTarget] = useState(scannedTargets[0] || "");
  const [geoCountry, setGeoCountry] = useState("US");

  // Batch state
  const [batchTargets, setBatchTargets] = useState(scannedTargets.slice(0, 3).join(", "));
  const [batchResult, setBatchResult] = useState<{ message: string; queued_run_ids: string[] } | null>(null);

  const run = async (fn: () => Promise<DigestResponse>) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await fn();
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
    setLoading(false);
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
        <h3>🤖 AI Intelligence Briefings</h3>
        <p className="digest-subtitle">
          Powered by <strong>TinyFish agent.run()</strong> — live browser research, structured output
        </p>
      </div>

      {/* Tabs */}
      <div className="digest-tabs">
        {[
          { id: "portfolio", label: "📊 Portfolio Brief" },
          { id: "entity",    label: "🏢 Entity Deep-Dive" },
          { id: "spike",     label: "📈 Risk Spike Explain" },
          { id: "geo",       label: "🌍 Geo-Targeted Scan" },
          { id: "batch",     label: "⚡ Batch Queue" },
        ].map(tab => (
          <button
            key={tab.id}
            className={`digest-tab ${activeTab === tab.id ? "digest-tab--active" : ""}`}
            onClick={() => { setActiveTab(tab.id as typeof activeTab); setResult(null); setError(null); }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="digest-body">
        {/* Portfolio briefing */}
        {activeTab === "portfolio" && (
          <div className="digest-form">
            <p className="digest-desc">
              Uses <code>agent.run()</code> to visit Reuters Legal and synthesise a plain-English weekly briefing
              for all monitored entities. Returns <strong>num_of_steps</strong> telemetry showing agent effort.
            </p>
            <button
              className="digest-run-btn"
              onClick={() => run(generatePortfolioDigest)}
              disabled={loading}
            >
              {loading ? "⏳ Generating…" : "📊 Generate Portfolio Briefing"}
            </button>
          </div>
        )}

        {/* Entity deep-dive */}
        {activeTab === "entity" && (
          <div className="digest-form">
            <p className="digest-desc">
              Uses <code>agent.run()</code> to visit SEC EDGAR and generate a structured risk narrative
              for a single entity, combining our findings with live SEC disclosures.
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
                onClick={() => run(() => generateEntityDigest(entityTarget))}
                disabled={loading || !entityTarget}
              >
                {loading ? "⏳ Researching…" : "🏢 Generate Entity Brief"}
              </button>
            </div>
          </div>
        )}

        {/* Risk spike */}
        {activeTab === "spike" && (
          <div className="digest-form">
            <p className="digest-desc">
              Uses <code>agent.run()</code> to explain WHY a risk score changed between two scans.
              Agent searches Reuters for news events between the two scan dates.
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
                onClick={() => run(() => generateRiskSpikeDigest(spikeTarget))}
                disabled={loading || !spikeTarget}
              >
                {loading ? "⏳ Analysing…" : "📈 Explain Risk Spike"}
              </button>
            </div>
          </div>
        )}

        {/* Geo-targeted scan */}
        {activeTab === "geo" && (
          <div className="digest-form">
            <p className="digest-desc">
              Uses <code>agent.run()</code> with <code>ProxyConfig(country_code=...)</code> to route
              the browser through a geo-targeted proxy, accessing jurisdiction-specific regulatory
              databases (FCA in GB, BaFin in DE, ASIC in AU, etc).
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
                onClick={() => run(() => geoScan(geoTarget, geoCountry))}
                disabled={loading || !geoTarget}
              >
                {loading ? "⏳ Scanning…" : "🌍 Run Geo-Scan"}
              </button>
            </div>
            <div className="digest-geo-note">
              ℹ️ Browser will exit from <strong>{GEO_OPTIONS.find(g => g.code === geoCountry)?.label}</strong>
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
              disabled={loading}
            >
              {loading ? "⏳ Queuing…" : "⚡ Queue Batch Enrichment"}
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
            ⚠ {error}
          </div>
        )}

        {/* Result card */}
        {result && activeTab !== "batch" && (
          <div className="digest-result-card">
            <div className="digest-result-meta">
              <span className="digest-type-badge">{result.digest_type.replace(/_/g, " ")}</span>
              {result.target && <span className="digest-result-target">· {result.target}</span>}
              <span className="digest-result-stats">
                {result.num_steps} steps · {result.duration_seconds?.toFixed(0)}s
                {result.run_id && <span> · <code className="digest-run-id-small">{result.run_id.slice(0, 12)}…</code></span>}
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
