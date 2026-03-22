import React from "react";
import type { Scan } from "../api/types";
import "./ScorePanel.css";

interface Props {
  scan: Scan;
}

const SEV_COLORS: Record<string, string> = {
  critical: "#f87171",
  high: "#fb923c",
  medium: "#fbbf24",
  low: "#4ade80",
};

export default function ScorePanel({ scan }: Props) {
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
        {(["critical", "high", "medium", "low"] as const).map((sev) => {
          const count = scan.source_results.reduce((acc, r) => acc, 0);
          return (
            <div key={sev} className="breakdown-row">
              <span className="breakdown-dot" style={{ background: SEV_COLORS[sev] }} />
              <span className="breakdown-label">{sev.charAt(0).toUpperCase() + sev.slice(1)}</span>
            </div>
          );
        })}
        <div className="breakdown-total">
          Total findings: <strong>{scan.findings_count}</strong>
        </div>
      </div>

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
                : "…"}
            </span>
          </div>
        ))}
      </div>
    </aside>
  );
}
