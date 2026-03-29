import React, { useEffect, useState } from "react";
import type { Scan } from "../api/types";
import { compareScans } from "../api/client";
import "./CompareModal.css";

interface Props {
  scans: Scan[];
  defaultScanId?: string;
  onClose: () => void;
}

function fmt(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number" && v > 10_000) {
    const m = v / 1_000_000;
    if (m >= 1) return `$${m.toFixed(1)}M`;
    return `$${(v / 1000).toFixed(0)}k`;
  }
  return String(v);
}

const RISK_COLOR: Record<string, string> = {
  critical: "#f87171",
  high: "#fb923c",
  medium: "#fbbf24",
  low: "#4ade80",
  Clean: "#4ade80",
};

export default function CompareModal({ scans, defaultScanId, onClose }: Props) {
  const completed = scans.filter((s) => s.status === "completed");
  const [scanA, setScanA] = useState(defaultScanId ?? completed[0]?.scan_id ?? "");
  const [scanB, setScanB] = useState(completed[1]?.scan_id ?? "");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canCompare = scanA && scanB && scanA !== scanB;

  const runCompare = async () => {
    if (!canCompare) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await compareScans(scanA, scanB));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (canCompare) runCompare();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const scanLabel = (id: string) => {
    const s = completed.find((x) => x.scan_id === id);
    return s ? `${s.target} (${new Date(s.created_at).toLocaleDateString()})` : id;
  };

  const sa = result?.scan_a as Record<string, unknown> | undefined;
  const sb = result?.scan_b as Record<string, unknown> | undefined;

  const deltaRisk = result?.delta_risk as number | undefined;
  const deltaFindings = result?.delta_findings as number | undefined;

  return (
    <>
      <div className="compare-overlay" onClick={onClose} />
      <div className="compare-modal" role="dialog" aria-label="Compare Scans">
        <div className="compare-modal-header">
          <h3>Compare Scans</h3>
          <button className="compare-close" onClick={onClose} type="button">✕</button>
        </div>

        {/* Pickers */}
        <div className="compare-pickers">
          <div className="compare-picker-group">
            <label className="compare-picker-label">Scan A</label>
            <select
              className="compare-select"
              value={scanA}
              onChange={(e) => setScanA(e.target.value)}
            >
              <option value="">— select —</option>
              {completed.map((s) => (
                <option key={s.scan_id} value={s.scan_id}>{scanLabel(s.scan_id)}</option>
              ))}
            </select>
          </div>
          <span className="compare-vs">vs</span>
          <div className="compare-picker-group">
            <label className="compare-picker-label">Scan B</label>
            <select
              className="compare-select"
              value={scanB}
              onChange={(e) => setScanB(e.target.value)}
            >
              <option value="">— select —</option>
              {completed.map((s) => (
                <option key={s.scan_id} value={s.scan_id}>{scanLabel(s.scan_id)}</option>
              ))}
            </select>
          </div>
          <button
            className="compare-run-btn"
            onClick={runCompare}
            disabled={!canCompare || loading}
            type="button"
          >
            {loading ? "…" : "Compare"}
          </button>
        </div>

        {error && <div className="compare-error">{error}</div>}

        {result && sa && sb && (
          <div className="compare-results">
            {/* Side-by-side summary */}
            <div className="compare-grid">
              {(["scan_a", "scan_b"] as const).map((key) => {
                const s = result[key] as Record<string, unknown>;
                const riskLabel = s.risk_label as string | undefined;
                return (
                  <div key={key} className="compare-card">
                    <div className="compare-card-target">{s.target as string}</div>
                    <div
                      className="compare-card-score"
                      style={{ color: RISK_COLOR[riskLabel ?? ""] ?? "#94a3b8" }}
                    >
                      {String(s.risk_score ?? "—")}
                      <span className="compare-card-score-unit">/100</span>
                    </div>
                    <div className="compare-card-label"
                      style={{ color: RISK_COLOR[riskLabel ?? ""] ?? "#94a3b8" }}>
                      {riskLabel ?? "—"}
                    </div>
                    <div className="compare-card-stats">
                      <span>{String(s.total_findings)} findings</span>
                      <span>${Number(s.total_exposure ?? 0).toLocaleString()} exposure</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Delta row */}
            <div className="compare-deltas">
              <div className={`compare-delta ${deltaRisk && deltaRisk > 0 ? "worse" : deltaRisk && deltaRisk < 0 ? "better" : "neutral"}`}>
                <span className="delta-label">Risk Δ</span>
                <span className="delta-value">
                  {deltaRisk != null ? (deltaRisk > 0 ? `+${deltaRisk}` : deltaRisk) : "—"}
                </span>
              </div>
              <div className={`compare-delta ${deltaFindings && deltaFindings > 0 ? "worse" : deltaFindings && deltaFindings < 0 ? "better" : "neutral"}`}>
                <span className="delta-label">Findings Δ</span>
                <span className="delta-value">
                  {deltaFindings != null ? (deltaFindings > 0 ? `+${deltaFindings}` : deltaFindings) : "—"}
                </span>
              </div>
              <div className="compare-delta neutral">
                <span className="delta-label">Shared cases</span>
                <span className="delta-value">{fmt(result.shared_case_ids)}</span>
              </div>
              <div className="compare-delta neutral">
                <span className="delta-label">Only in A</span>
                <span className="delta-value">{fmt(result.unique_to_a)}</span>
              </div>
              <div className="compare-delta neutral">
                <span className="delta-label">Only in B</span>
                <span className="delta-value">{fmt(result.unique_to_b)}</span>
              </div>
              <div className="compare-delta neutral">
                <span className="delta-label">Exposure Δ</span>
                <span className="delta-value">{fmt(result.delta_exposure)}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
