import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Persona, ScanRequest } from "../api/types";
import {
  ChevronDown, ChevronRight, Zap, Rocket,
  Check, ShieldCheck, BarChart2, Leaf, Scale, Search, Factory,
} from "lucide-react";
import { createScan, listPersonas } from "../api/client";
import "./NewScan.css";

// Maps backend icon IDs (from persona.py) to Lucide components
const PERSONA_ICON_MAP: Record<string, React.ReactNode> = {
  "shield-check": <ShieldCheck size={22} />,
  "bar-chart-2":  <BarChart2  size={22} />,
  "leaf":         <Leaf       size={22} />,
  "scale":        <Scale      size={22} />,
  "search":       <Search     size={22} />,
  "factory":      <Factory    size={22} />,
};

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
  personaId: string | null;
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

  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersona, setSelectedPersona] = useState<Persona | null>(null);

  const [form, setForm] = useState<FormState>({
    target: "",
    query: "",
    sources: ALL_SOURCES.map((s) => s.id),
    maxAgents: 5,
    personaId: null,
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // ── Load personas on mount
  useEffect(() => {
    listPersonas()
      .then(setPersonas)
      .catch(() => setPersonas([]));
  }, []);

  // ── Persona selection
  const selectPersona = (p: Persona | null) => {
    setSelectedPersona(p);
    if (p) {
      setForm((prev) => ({
        ...prev,
        personaId: p.id,
        sources: p.default_sources,
        query: p.default_query,
      }));
    } else {
      setForm((prev) => ({
        ...prev,
        personaId: null,
        sources: ALL_SOURCES.map((s) => s.id),
        query: "",
      }));
    }
  };

  const selectDemoTarget = (name: string) => {
    setForm((prev) => ({ ...prev, target: name }));
  };

  // ── Source toggling
  const toggleSource = (id: string) => {
    setForm((prev) => ({
      ...prev,
      sources: prev.sources.includes(id)
        ? prev.sources.filter((s) => s !== id)
        : [...prev.sources, id],
    }));
  };

  // ── Submit
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
        persona_id: form.personaId ?? undefined,
        max_concurrent_agents: form.maxAgents,
      };
      const scan = await createScan(req);
      navigate(`/?scan_id=${scan.scan_id}`);
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  };

  // ── Render
  // Step completion state
  const step1Done = selectedPersona !== null;
  const step2Done = form.target.trim().length >= 2;
  const activeStep = !step1Done ? 1 : !step2Done ? 2 : 3;

  return (
    <main className="new-scan-page">
      <div className="new-scan-card">
        <header className="new-scan-header">
          <h2>New Diligence Scan</h2>
          <p>Choose a role, pick a target, and launch a multi-agent regulatory sweep.</p>
          <div className="step-progress" aria-label="Setup progress">
            {[
              { n: 1, label: "Choose Role" },
              { n: 2, label: "Target Entity" },
              { n: 3, label: "Sources & Launch" },
            ].map(({ n, label }) => (
              <div
                key={n}
                className={`step-item ${activeStep === n ? "step-item--active" : ""} ${activeStep > n ? "step-item--done" : ""}`}
              >
                <div className="step-circle">
                  {activeStep > n ? <Check size={12} aria-hidden /> : n}
                </div>
                <span className="step-label">{label}</span>
                {n < 3 && <div className="step-line" />}
              </div>
            ))}
          </div>
        </header>

        {/* ── Step 1: Persona selector */}
        <section className="persona-section">
          <h3 className="section-title">Step 1: Choose your role</h3>
          <div className="persona-grid">
            {personas.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`persona-card ${selectedPersona?.id === p.id ? "persona-card--active" : ""}`}
                style={{ "--persona-color": p.color } as React.CSSProperties}
                onClick={() => selectPersona(selectedPersona?.id === p.id ? null : p)}
                disabled={submitting}
              >
                <span className="persona-icon">
                  {PERSONA_ICON_MAP[p.icon] ?? <ShieldCheck size={22} />}
                </span>
                <span className="persona-label">{p.label}</span>
                <span className="persona-desc">{p.description}</span>
                <div className="persona-focus">
                  {p.focus_areas.map((f) => (
                    <span key={f} className="focus-tag">{f}</span>
                  ))}
                </div>
              </button>
            ))}
          </div>
        </section>

        <form className="new-scan-form" onSubmit={handleSubmit} noValidate>
          {/* ── Step 2: Target */}
          <section className="target-section">
            <h3 className="section-title">Step 2: Enter target entity</h3>

            {/* Demo quick-start targets */}
            {selectedPersona && selectedPersona.demo_targets.length > 0 && (
              <div className="demo-targets">
                <span className="demo-label">Quick start:</span>
                {selectedPersona.demo_targets.map((dt) => (
                  <button
                    key={dt.name}
                    type="button"
                    className={`demo-target-btn ${form.target === dt.name ? "demo-target-btn--active" : ""}`}
                    onClick={() => selectDemoTarget(dt.name)}
                    disabled={submitting}
                    title={dt.description}
                  >
                    {dt.name}
                  </button>
                ))}
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="target">
                Entity Name <span className="required">*</span>
              </label>
              <input
                id="target"
                className="form-input"
                type="text"
                placeholder="e.g. Tesla Inc, Johnson & Johnson, Boeing Company"
                value={form.target}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, target: e.target.value }))
                }
                disabled={submitting}
                autoFocus
                required
              />
            </div>
          </section>

          {/* ── Advanced settings toggle */}
          <button
            type="button"
            className="advanced-toggle"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            {showAdvanced ? "Hide" : "Show"} advanced settings
          </button>

          {showAdvanced && (
            <div className="advanced-section">
              {/* Query override */}
              <div className="form-group">
                <label className="form-label" htmlFor="query">
                  Research Focus
                  <span className="form-hint"> (auto-set by persona)</span>
                </label>
                <textarea
                  id="query"
                  className="form-input form-textarea"
                  placeholder="e.g. workplace safety violations last 5 years"
                  value={form.query}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, query: e.target.value }))
                  }
                  disabled={submitting}
                  rows={3}
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
                  Max Concurrent Agents
                  <span className="form-hint"> ({form.maxAgents})</span>
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
            </div>
          )}

          {/* Summary strip */}
          {form.target.trim() && (
            <div className="scan-summary">
              <div className="summary-icon"><Zap size={16} /></div>
              <div className="summary-text">
                <strong>Ready:</strong> Research{" "}
                <em>{form.target.trim()}</em> across{" "}
                <strong>{form.sources.length}</strong> regulatory source
                {form.sources.length !== 1 && "s"}
                {selectedPersona && (
                  <>
                    {" "}as <strong>{selectedPersona.label}</strong>{" "}
                    {PERSONA_ICON_MAP[selectedPersona.icon] ?? <ShieldCheck size={16} />}
                  </>
                )}
              </div>
            </div>
          )}

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
                  <Rocket size={14} /> Start Scan
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
