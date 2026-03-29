import React from "react";
import { X } from "lucide-react";
import type { Finding } from "../api/types";
import "./DetailsDrawer.css";

interface Props {
  finding: Finding;
  onClose: () => void;
}

function formatPenalty(amount: number): string {
  if (!amount) return "None stated";
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(2)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(0)}k`;
  return `$${amount.toLocaleString()}`;
}

export default function DetailsDrawer({ finding, onClose }: Props) {
  return (
    <>
      <div className="drawer-overlay" onClick={onClose} aria-hidden />
      <aside className="details-drawer" role="complementary" aria-label="Case details">
        <div className="details-header">
          <h3>Case details · {finding.case_id}</h3>
          <button className="drawer-close" onClick={onClose} aria-label="Close" type="button">
            <X size={14} />
          </button>
        </div>

        <span className={`sev-badge sev-badge--${finding.severity}`}>
          ● {finding.severity.charAt(0).toUpperCase() + finding.severity.slice(1)}
        </span>

        <div className="details-grid">
          <span className="dl">Entity</span>
          <span className="dv">{finding.entity_name || "—"}</span>

          <span className="dl">Violation</span>
          <span className="dv">{finding.violation_type}</span>

          <span className="dl">Jurisdiction</span>
          <span className="dv">{finding.jurisdiction || "—"}</span>

          <span className="dl">Source</span>
          <span className="dv">{finding.source_id}</span>

          <span className="dl">Decision date</span>
          <span className="dv">{finding.decision_date || "—"}</span>

          <span className="dl">Status</span>
          <span className="dv" style={{ textTransform: "capitalize" }}>{finding.status}</span>

          <span className="dl">Exposure</span>
          <span className="dv">{formatPenalty(finding.penalty_amount)}</span>
        </div>

        {finding.description && (
          <div className="details-description">
            <div className="details-description-label">Description</div>
            <p>{finding.description}</p>
          </div>
        )}

        {finding.source_url && (
          <a
            href={finding.source_url}
            className="details-link"
            target="_blank"
            rel="noopener noreferrer"
          >
            View source document →
          </a>
        )}
      </aside>
    </>
  );
}
