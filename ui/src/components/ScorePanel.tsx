import React from "react";
import type { Finding, Scan } from "../api/types";
import "./ScorePanel.css";

interface Props {
  scan: Scan;
  findings?: Finding[];
}

const SEV_COLORS: Record<string, string> = {
  critical: "#f87171",
  high: "#fb923c",
  medium: "#fbbf24",
  low: "#4ade80",
};

export default function ScorePanel({ scan, findings = [] }: Props) {
  const score = scan.risk_score ?? 0;
  const label = scan.risk_label ?? "—";

  // Gauge arc: stroke-dasharray trick on a 120-deg arc
  const circumference = 2 * Math.PI * 40;
  const filled = (score / 100) * circumference * 0.75;
  const gap = circumference - filled;

  const scoreColor =
    score >= 70
      ? "#f87171"
      : score >= 40
      ? "#fb923c"
      : score >= 15
      ? "#fbbf24"
      : "#4ade80";

  // Severity breakdown counts from actual findings
  const sevCounts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  findings.forEach((f) => {
    if (sevCounts[f.severity] !== undefined) sevCounts[f.severity]++;
  });

  // Source × Severity heatmap data
  const sourceIds = [...new Set(findings.map((f) => f.source_id))];
  const heatmap: Record<string, Record<string, number>> = {};
  sourceIds.forEach((sid) => {
    heatmap[sid] = { critical: 0, high: 0, medium: 0, low: 0 };
  });
  findings.forEach((f) => {
    if (heatmap[f.source_id]) heatmap[f.source_id][f.severity]++;
  });

  // Elapsed time
  const elapsed = scan.completed_at
    ? Math.round(
        (new Date(scan.completed_at).getTime() - new Date(scan.created_at).getTime()) / 1000
      )
    : null;

  return (
    <aside className="score-panel">
      <div className="score-panel-title">Risk Score</div>

      <div className="gauge-wrap">
        <svg viewBox="0 0 100 70" className="gauge-svg" aria-hidden>
          {/* Track */}
          <path
            d="M 10 60 A 40 40 0 1 1 90 60"
            fill="none"
            stroke="var(--border-subtle)"
            strokeWidth="8"
            strokeLinecap="round"
          />
          {/* Fill */}
          {scan.status === "completed" && (
            <path
              d="M 10 60 A 40 40 0 1 1 90 60"
              fill="none"
              stroke={scoreColor}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={`${filled} ${gap}`}
              style={{ transition: "stroke-dasharray 800ms ease" }}
            />
          )}
        </svg>
        <div className="gauge-label">
          <span className="gauge-number" style={{ color: scoreColor }}>
            {scan.status === "completed" ? score : "—"}
          </span>
          <span className="gauge-sub">{label}</span>
        </div>
      </div>

      <div className="score-breakdown">
        <div className="breakdown-title">Findings breakdown</div>
        {(["critical", "high", "medium", "low"] as const).map((sev) => (
          <div key={sev} className="breakdown-row">
            <span className="breakdown-dot" style={{ background: SEV_COLORS[sev] }} />
            <span className="breakdown-label">{sev.charAt(0).toUpperCase() + sev.slice(1)}</span>
            <span className="breakdown-count" style={{ color: SEV_COLORS[sev] }}>
              {sevCounts[sev]}
            </span>
          </div>
        ))}
        <div className="breakdown-total">
          Total findings: <strong>{scan.findings_count}</strong>
        </div>
      </div>

      {/* Risk heatmap — Source × Severity */}
      {sourceIds.length > 0 && (
        <div className="heatmap-section">
          <div className="breakdown-title">Risk Heatmap</div>
          <div className="heatmap-grid" style={{ gridTemplateColumns: `80px repeat(4, 1fr)` }}>
            <span className="heatmap-corner" />
            {(["critical", "high", "medium", "low"] as const).map((s) => (
              <span key={s} className="heatmap-col-head" style={{ color: SEV_COLORS[s] }}>
                {s.charAt(0).toUpperCase()}
              </span>
            ))}
            {sourceIds.map((sid) => (
              <React.Fragment key={sid}>
                <span className="heatmap-row-head">{sid.replace("us_", "").toUpperCase()}</span>
                {(["critical", "high", "medium", "low"] as const).map((sev) => {
                  const count = heatmap[sid][sev];
                  const opacity = count === 0 ? 0.05 : Math.min(0.15 + count * 0.2, 0.9);
                  return (
                    <span
                      key={sev}
                      className="heatmap-cell"
                      style={{
                        background: SEV_COLORS[sev],
                        opacity,
                      }}
                      title={`${sid} — ${sev}: ${count}`}
                    >
                      {count > 0 ? count : ""}
                    </span>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      {/* Source status bars */}
      <div className="source-bars">
        <div className="breakdown-title">Sources</div>
        {scan.source_results.map((r) => (
          <div key={r.source_id} className="source-bar-row">
            <span className="source-name">{r.source_id}</span>
            <span
              className={`source-status ${
                r.status === "completed"
                  ? "source-status--ok"
                  : r.status === "failed"
                  ? "source-status--fail"
                  : "source-status--pending"
              }`}
            >
              {r.status === "completed"
                ? `${r.records_found} records`
                : r.status === "failed"
                ? "Error"
                : "..."}
            </span>
          </div>
        ))}
      </div>

      {/* Scan timing */}
      {elapsed !== null && (
        <div className="scan-timing">
          <div className="breakdown-title">Performance</div>
          <div className="timing-row">
            <span className="timing-label">Duration</span>
            <span className="timing-value">{elapsed}s</span>
          </div>
          <div className="timing-row">
            <span className="timing-label">Sources</span>
            <span className="timing-value">{scan.sources_completed}/{scan.sources_total}</span>
          </div>
          {scan.persona_id && (
            <div className="timing-row">
              <span className="timing-label">Persona</span>
              <span className="timing-value" style={{ textTransform: "capitalize" }}>
                {scan.persona_id.replace(/_/g, " ")}
              </span>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
