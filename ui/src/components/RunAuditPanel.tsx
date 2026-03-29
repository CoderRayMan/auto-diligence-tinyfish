import React, { useEffect, useState, useCallback } from "react";
import { listRuns, getRunStats, getRun } from "../api/client";
import type { RunSummary, RunDetail, RunStats } from "../api/types";
import "./RunAuditPanel.css";

const STATUS_COLORS: Record<string, string> = {
  COMPLETED: "#22c55e",
  FAILED: "#ef4444",
  RUNNING: "#3b82f6",
  PENDING: "#f59e0b",
  CANCELLED: "#9ca3af",
};

export const RunAuditPanel: React.FC = () => {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [stats, setStats] = useState<RunStats | null>(null);
  const [selected, setSelected] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [cursor, setCursor] = useState<string | undefined>(undefined);

  const loadRuns = useCallback(async (nextCursor?: string) => {
    setLoading(true);
    try {
      const [resp, statsResp] = await Promise.all([
        listRuns({ status: filterStatus || undefined, limit: 25, cursor: nextCursor }),
        !nextCursor ? getRunStats(100) : Promise.resolve(null),
      ]);
      setRuns(prev => nextCursor ? [...prev, ...resp.runs] : resp.runs);
      setHasMore(resp.has_more);
      setCursor(resp.next_cursor ?? undefined);
      if (statsResp) setStats(statsResp);
    } catch {
      /* ignore */
    }
    setLoading(false);
  }, [filterStatus]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  const handleSelectRun = async (runId: string) => {
    try {
      const detail = await getRun(runId);
      setSelected(detail);
    } catch {
      /* ignore */
    }
  };

  const formatDuration = (s?: number) => {
    if (s == null) return "—";
    if (s < 60) return `${s.toFixed(0)}s`;
    return `${(s / 60).toFixed(1)}m`;
  };

  return (
    <div className="run-audit-panel">
      {/* Header + stats */}
      <div className="run-audit-header">
        <div>
          <h3>🔍 TinyFish Run Audit</h3>
          <p className="run-audit-subtitle">Every browser agent run, fully transparent</p>
        </div>
        {stats && (
          <div className="run-audit-stats">
            <div className="run-stat-chip">
              <span className="run-stat-val">{stats.total_runs}</span>
              <span className="run-stat-label">Total Runs</span>
            </div>
            <div className="run-stat-chip" style={{ borderColor: "#22c55e" }}>
              <span className="run-stat-val" style={{ color: "#22c55e" }}>{stats.success_rate_pct}%</span>
              <span className="run-stat-label">Success Rate</span>
            </div>
            <div className="run-stat-chip">
              <span className="run-stat-val">{formatDuration(stats.avg_duration_seconds)}</span>
              <span className="run-stat-label">Avg Duration</span>
            </div>
            <div className="run-stat-chip" style={{ borderColor: "#3b82f6" }}>
              <span className="run-stat-val" style={{ color: "#3b82f6" }}>{stats.pending_or_running}</span>
              <span className="run-stat-label">Active</span>
            </div>
          </div>
        )}
      </div>

      {/* Filter bar */}
      <div className="run-audit-filters">
        <select
          value={filterStatus}
          onChange={e => { setFilterStatus(e.target.value); }}
          className="run-status-filter"
        >
          <option value="">All statuses</option>
          <option value="COMPLETED">Completed</option>
          <option value="FAILED">Failed</option>
          <option value="RUNNING">Running</option>
          <option value="PENDING">Pending</option>
          <option value="CANCELLED">Cancelled</option>
        </select>
        <button className="run-refresh-btn" onClick={() => loadRuns()} disabled={loading}>
          {loading ? "⏳" : "↻"} Refresh
        </button>
      </div>

      {/* Two-pane layout */}
      <div className="run-audit-body">
        {/* Left: run list */}
        <div className="run-list">
          {loading && runs.length === 0 ? (
            <div className="run-list-loading">Loading runs…</div>
          ) : runs.length === 0 ? (
            <div className="run-list-empty">No TinyFish runs found yet.<br />Start a scan to generate runs.</div>
          ) : (
            <>
              {runs.map(run => (
                <div
                  key={run.run_id}
                  className={`run-list-item ${selected?.run_id === run.run_id ? "run-list-item--active" : ""}`}
                  onClick={() => handleSelectRun(run.run_id)}
                >
                  <div className="run-list-item-top">
                    <span
                      className="run-status-badge"
                      style={{ background: STATUS_COLORS[run.status] || "#6b7280" }}
                    >
                      {run.status}
                    </span>
                    <span className="run-duration">{formatDuration(run.duration_seconds)}</span>
                  </div>
                  <div className="run-goal-preview">{run.goal_preview}</div>
                  <div className="run-meta">
                    {run.created_at ? new Date(run.created_at).toLocaleString() : ""}
                    {run.error_message && (
                      <span className="run-error-chip"> ⚠ {run.error_message.slice(0, 40)}</span>
                    )}
                  </div>
                </div>
              ))}
              {hasMore && (
                <button className="run-load-more" onClick={() => loadRuns(cursor)}>
                  Load more…
                </button>
              )}
            </>
          )}
        </div>

        {/* Right: detail pane */}
        <div className="run-detail-pane">
          {selected ? (
            <>
              <div className="run-detail-header">
                <span
                  className="run-status-badge"
                  style={{ background: STATUS_COLORS[selected.status] || "#6b7280" }}
                >
                  {selected.status}
                </span>
                <code className="run-id-code">{selected.run_id}</code>
              </div>

              {/* Live stream embed */}
              {selected.streaming_url && (
                <div className="run-stream-embed-wrap">
                  <div className="run-stream-label">
                    <span className="run-stream-dot" /> Live Browser
                  </div>
                  <iframe
                    src={selected.streaming_url}
                    className="run-stream-iframe"
                    title="TinyFish Live Browser"
                    sandbox="allow-same-origin allow-scripts"
                  />
                </div>
              )}

              <div className="run-detail-section">
                <div className="run-detail-label">Goal</div>
                <div className="run-detail-goal">{selected.goal}</div>
              </div>

              <div className="run-detail-grid">
                <div>
                  <div className="run-detail-label">Created</div>
                  <div>{selected.created_at ? new Date(selected.created_at).toLocaleString() : "—"}</div>
                </div>
                <div>
                  <div className="run-detail-label">Duration</div>
                  <div>{formatDuration(selected.duration_seconds)}</div>
                </div>
                {selected.proxy_country && (
                  <div>
                    <div className="run-detail-label">Geo Proxy</div>
                    <div>🌍 {selected.proxy_country}</div>
                  </div>
                )}
                {selected.error_category && (
                  <div>
                    <div className="run-detail-label">Error Type</div>
                    <div className="run-error-text">{selected.error_category}: {selected.error_message}</div>
                  </div>
                )}
              </div>

              {selected.result && (
                <div className="run-detail-section">
                  <div className="run-detail-label">Result JSON</div>
                  <pre className="run-result-json">
                    {JSON.stringify(selected.result, null, 2)}
                  </pre>
                </div>
              )}
            </>
          ) : (
            <div className="run-detail-empty">
              ← Select a run to inspect its goal, result, and live browser stream
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RunAuditPanel;
