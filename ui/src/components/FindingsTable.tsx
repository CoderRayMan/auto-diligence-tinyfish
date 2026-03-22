import React, { useState } from "react";
import type { Finding } from "../api/types";
import DetailsDrawer from "./DetailsDrawer";
import "./FindingsTable.css";

interface Props {
  findings: Finding[];
  loading?: boolean;
}

const SEV_CLASS: Record<string, string> = {
  critical: "sev--critical",
  high: "sev--high",
  medium: "sev--medium",
  low: "sev--low",
};

const STATUS_CLASS: Record<string, string> = {
  open: "status--open",
  settled: "status--settled",
  closed: "status--closed",
  appealed: "status--appealed",
  unknown: "status--unknown",
};

function formatPenalty(amount: number): string {
  if (!amount) return "—";
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(0)}k`;
  return `$${amount}`;
}

export default function FindingsTable({ findings, loading }: Props) {
  const [selected, setSelected] = useState<Finding | null>(null);
  const [sortKey, setSortKey] = useState<"severity" | "penalty_amount" | "decision_date">("severity");
  const [sortAsc, setSortAsc] = useState(false);

  const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

  const sorted = [...findings].sort((a, b) => {
    let cmp = 0;
    if (sortKey === "severity") {
      cmp = (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9);
    } else if (sortKey === "penalty_amount") {
      cmp = a.penalty_amount - b.penalty_amount;
    } else {
      cmp = a.decision_date.localeCompare(b.decision_date);
    }
    return sortAsc ? cmp : -cmp;
  });

  function toggleSort(key: typeof sortKey) {
    if (sortKey === key) setSortAsc((v) => !v);
    else { setSortKey(key); setSortAsc(false); }
  }

  return (
    <section className="findings-panel">
      <div className="section-header">
        <span>Findings · Prioritised by risk</span>
        <div className="sort-pills">
          {(["severity", "penalty_amount", "decision_date"] as const).map((k) => (
            <button
              key={k}
              className={`sort-pill ${sortKey === k ? "sort-pill--active" : ""}`}
              onClick={() => toggleSort(k)}
              type="button"
            >
              {k === "penalty_amount" ? "Penalty" : k === "decision_date" ? "Date" : "Severity"}
              {sortKey === k && (sortAsc ? " ↑" : " ↓")}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="findings-empty">Loading findings…</div>
      ) : findings.length === 0 ? (
        <div className="findings-empty">No findings yet. Run a scan to see results.</div>
      ) : (
        <div className="table-scroll">
          <table className="findings-table">
            <thead>
              <tr>
                <th style={{ width: 80 }}>Severity</th>
                <th>Case / matter</th>
                <th style={{ width: 120 }}>Jurisdiction</th>
                <th style={{ width: 120 }}>Source</th>
                <th style={{ width: 80 }}>Status</th>
                <th style={{ width: 100 }}>Decision date</th>
                <th style={{ width: 80 }}>Exposure</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((f) => (
                <tr
                  key={f.finding_id}
                  className="finding-row"
                  onClick={() => setSelected(f)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && setSelected(f)}
                >
                  <td>
                    <span className={`sev-pill ${SEV_CLASS[f.severity] ?? ""}`}>
                      ● {f.severity}
                    </span>
                  </td>
                  <td className="case-desc">{f.description || f.violation_type}</td>
                  <td className="cell-soft">{f.jurisdiction || "—"}</td>
                  <td className="cell-soft">{f.source_id}</td>
                  <td>
                    <span className={`status-pill ${STATUS_CLASS[f.status] ?? ""}`}>
                      {f.status}
                    </span>
                  </td>
                  <td className="cell-soft">{f.decision_date || "—"}</td>
                  <td className="cell-penalty">{formatPenalty(f.penalty_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <DetailsDrawer finding={selected} onClose={() => setSelected(null)} />
      )}
    </section>
  );
}
