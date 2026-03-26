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

function elapsedStr(scan: Scan): string | null {
  const end = scan.completed_at ?? new Date().toISOString();
  const ms = new Date(end).getTime() - new Date(scan.created_at).getTime();
  if (ms < 0) return null;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

const PERSONA_LABELS: Record<string, string> = {
  compliance_officer: "Compliance Officer",
  m_and_a_analyst: "M&A Analyst",
  esg_researcher: "ESG Researcher",
  legal_counsel: "Legal Counsel",
  investigative_journalist: "Investigative Journalist",
  supply_chain_auditor: "Supply Chain Auditor",
};

export default function ContextStrip({ scan }: Props) {
  const pct = progressPct(scan);
  const isRunning = scan.status === "running" || scan.status === "pending";
  const elapsed = elapsedStr(scan);

  return (
    <section className="context-strip">
      <div className="context-main">
        <h2>{scan.target} · Diligence Run</h2>
        <div className="context-subtitle">
          {scan.persona_id && PERSONA_LABELS[scan.persona_id]
            ? `${PERSONA_LABELS[scan.persona_id]} perspective · `
            : "M&A buyer view · "}
          Legal, regulatory, workplace safety, and enforcement history
        </div>
        <div className="chip-row">
          <span className="chip chip--accent">Sources: {scan.sources_total} regulatory portals</span>
          <span className="chip">Scope: Litigation &amp; Enforcement</span>
          {scan.persona_id && (
            <span className="chip chip--persona">
              {PERSONA_LABELS[scan.persona_id] ?? scan.persona_id}
            </span>
          )}
          {scan.risk_label && (
            <span className="chip chip--risk">{scan.risk_label}</span>
          )}
        </div>
      </div>

      <div className="context-meta">
        {isRunning ? (
          <div className="pill pill--running">
            ● Scan running – {scan.sources_completed}/{scan.sources_total} sites complete
            {elapsed && <span className="pill-elapsed"> · {elapsed}</span>}
          </div>
        ) : scan.status === "completed" ? (
          <div className="pill pill--done">
            ✓ Scan complete
            {elapsed && <span className="pill-elapsed"> · {elapsed}</span>}
          </div>
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
