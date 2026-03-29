import React from "react";
import type { Finding } from "../api/types";
import "./Timeline.css";

interface Props {
  findings: Finding[];
  onSelect?: (finding: Finding) => void;
}

const SEV_COLORS: Record<string, string> = {
  critical: "#f87171",
  high: "#fb923c",
  medium: "#fbbf24",
  low: "#4ade80",
};

/**
 * Chronological timeline of findings grouped by month/year.
 * Great for spotting patterns and clusters of enforcement actions.
 */
export default function Timeline({ findings, onSelect }: Props) {
  // Sort by date descending
  const sorted = [...findings]
    .filter((f) => f.decision_date)
    .sort((a, b) => b.decision_date.localeCompare(a.decision_date));

  if (sorted.length === 0) return null;

  // Group by year-month
  const groups: Record<string, Finding[]> = {};
  sorted.forEach((f) => {
    const key = f.decision_date.slice(0, 7) || "Unknown";
    if (!groups[key]) groups[key] = [];
    groups[key].push(f);
  });

  const months = Object.keys(groups).sort().reverse();

  return (
    <div className="timeline-panel">
      <div className="timeline-header">Timeline · {sorted.length} dated finding{sorted.length !== 1 && "s"}</div>
      <div className="timeline-track">
        {months.map((month) => (
          <div key={month} className="timeline-group">
            <div className="timeline-month">
              {new Date(month + "-01").toLocaleDateString("en-US", {
                year: "numeric",
                month: "short",
              })}
            </div>
            <div className="timeline-items">
              {groups[month].map((f) => (
                <button
                  key={f.finding_id}
                  className="timeline-item"
                  onClick={() => onSelect?.(f)}
                  type="button"
                  title={`${f.violation_type} — ${f.entity_name}`}
                >
                  <span
                    className="timeline-dot"
                    style={{ background: SEV_COLORS[f.severity] ?? "#6b7280" }}
                  />
                  <span className="timeline-desc">
                    <span className="timeline-title">{f.violation_type || f.case_id}</span>
                    <span className="timeline-meta">
                      {f.source_id} · {f.severity}
                      {f.penalty_amount > 0 &&
                        ` · $${f.penalty_amount >= 1_000_000
                          ? `${(f.penalty_amount / 1_000_000).toFixed(1)}M`
                          : f.penalty_amount >= 1_000
                          ? `${(f.penalty_amount / 1_000).toFixed(0)}k`
                          : f.penalty_amount}`}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
