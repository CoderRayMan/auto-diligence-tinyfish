import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ScanRequest } from "../api/types";
import { createScan } from "../api/client";
import "./NewScan.css";

const ALL_SOURCES = [
  { id: "us_osha", label: "OSHA", description: "Occupational Safety violations" },
  { id: "us_fda", label: "FDA", description: "FDA enforcement actions & recalls" },
  { id: "us_sec", label: "SEC", description: "Securities & fraud enforcement" },
  { id: "us_dol", label: "DOL", description: "Department of Labor violations" },
  { id: "us_epa", label: "EPA", description: "Environmental enforcement" },
];

interface FormState {
  target: string;
  query: string;
  sources: string[];
  maxAgents: number;
}

function validate(f: FormState): string | null {
  if (!f.target.trim() || f.target.trim().length < 2) {
    return "Entity name must be at least 2 characters.";
  }
  if (f.sources.length === 0) {
    return "Select at least one regulatory source.";
  }
  return null;
}

export default function NewScan() {
  const navigate = useNavigate();

  const [form, setForm] = useState<FormState>({
    target: "",
    query: "",
    sources: ALL_SOURCES.map((s) => s.id),
    maxAgents: 5,
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // ---------------------------------------------------------------- helpers

  const toggleSource = (id: string) => {
    setForm((prev) => ({
      ...prev,
      sources: prev.sources.includes(id)
        ? prev.sources.filter((s) => s !== id)
        : [...prev.sources, id],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validate(form);
    if (err) {
      setFormError(err);
      return;
    }
    setFormError(null);
    setSubmitting(true);

    try {
      const req: ScanRequest = {
        target: form.target.trim(),
        query: form.query.trim() || undefined,
        sources: form.sources,
        max_concurrent_agents: form.maxAgents,
      };
      const scan = await createScan(req);
      navigate(`/?scan_id=${scan.scan_id}`);
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  };

  // ---------------------------------------------------------------- render

  return (
    <main className="new-scan-page">
      <div className="new-scan-card">
        <header className="new-scan-header">
          <h2>New Diligence Scan</h2>
          <p>Configure a multi-source regulatory research run for an entity.</p>
        </header>

        <form className="new-scan-form" onSubmit={handleSubmit} noValidate>
          {/* Target */}
          <div className="form-group">
            <label className="form-label" htmlFor="target">
              Entity Name <span className="required">*</span>
            </label>
            <input
              id="target"
              className="form-input"
              type="text"
              placeholder="e.g. Acme Corporation"
              value={form.target}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, target: e.target.value }))
              }
              disabled={submitting}
              autoFocus
              required
            />
          </div>

          {/* Query */}
          <div className="form-group">
            <label className="form-label" htmlFor="query">
              Research Focus{" "}
              <span className="form-hint">(optional)</span>
            </label>
            <input
              id="query"
              className="form-input"
              type="text"
              placeholder="e.g. workplace safety violations last 5 years"
              value={form.query}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, query: e.target.value }))
              }
              disabled={submitting}
            />
          </div>

          {/* Sources */}
          <fieldset className="form-group">
            <legend className="form-label">
              Regulatory Sources <span className="required">*</span>
            </legend>
            <div className="sources-grid">
              {ALL_SOURCES.map((src) => {
                const checked = form.sources.includes(src.id);
                return (
                  <label
                    key={src.id}
                    className={`source-chip ${checked ? "source-chip--on" : ""}`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleSource(src.id)}
                      disabled={submitting}
                    />
                    <span className="source-chip-label">{src.label}</span>
                    <span className="source-chip-desc">{src.description}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          {/* Max concurrent agents */}
          <div className="form-group">
            <label className="form-label" htmlFor="maxAgents">
              Max Concurrent Agents{" "}
              <span className="form-hint">({form.maxAgents})</span>
            </label>
            <input
              id="maxAgents"
              className="form-range"
              type="range"
              min={1}
              max={10}
              value={form.maxAgents}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  maxAgents: Number(e.target.value),
                }))
              }
              disabled={submitting}
            />
            <div className="range-labels">
              <span>1 (sequential)</span>
              <span>10 (max parallel)</span>
            </div>
          </div>

          {/* Form error */}
          {formError && (
            <div className="form-error" role="alert">
              {formError}
            </div>
          )}

          {/* Actions */}
          <div className="form-actions">
            <button
              className="ghost-btn"
              type="button"
              onClick={() => navigate(-1)}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              className="primary-btn"
              type="submit"
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <span className="btn-spinner" />
                  Starting…
                </>
              ) : (
                <>
                  <span className="icon">▶</span> Start Scan
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
