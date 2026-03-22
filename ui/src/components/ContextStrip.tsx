import React from "react";
import type { Scan } from "../api/types";
import "./ContextStrip.css";

interface Props {
  scan: Scan;
}

function progressPct(scan: Scan): number {
  if (scan.sources_total === 0) return 0;
  return Math.round((scan.sources_completed / scan.sources_total) * 100);
}

export default function ContextStrip({ scan }: Props) {
  const pct = progressPct(scan);
  const isRunning = scan.status === "running" || scan.status === "pending";

  return (
    <section className="context-strip">
      <div className="context-main">
        <h2>{scan.target} · Diligence Run</h2>
        <div className="context-subtitle">
          M&A buyer view · Legal, regulatory, workplace safety, and enforcement history
        </div>
        <div className="chip-row">
          <span className="chip chip--accent">Sources: {scan.sources_total} regulatory portals</span>
          <span className="chip">Scope: Litigation &amp; Enforcement</span>
          {scan.risk_label && (
            <span className="chip chip--risk">{scan.risk_label}</span>
          )}
        </div>
      </div>

      <div className="context-meta">
        {isRunning ? (
          <div className="pill pill--running">
            ● Scan running – {scan.sources_completed}/{scan.sources_total} sites complete
          </div>
        ) : scan.status === "completed" ? (
          <div className="pill pill--done">✓ Scan complete</div>
        ) : scan.status === "failed" ? (
          <div className="pill pill--failed">✕ Scan failed</div>
        ) : (
          <div className="pill pill--pending">◌ Pending</div>
        )}

        {isRunning && (
          <div className="progress-bar-wrap">
            <div className="progress-bar" style={{ width: `${pct}%` }} />
          </div>
        )}

        {scan.completed_at && (
          <div className="meta-time">
            Completed: {new Date(scan.completed_at).toLocaleString()}
          </div>
        )}
      </div>
    </section>
  );
}
