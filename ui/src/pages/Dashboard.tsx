import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { AgentEvent, Finding, Scan } from "../api/types";
import {
  cancelScan,
  getAgentEventHistory,
  getFindings,
  getScan,
  listScans,
  subscribeAgentEvents,
  rerunScan,
  getExecutiveReport,
} from "../api/client";
import BrowserGrid from "../components/BrowserGrid";
import ContextStrip from "../components/ContextStrip";
import FindingsTable from "../components/FindingsTable";
import ScorePanel from "../components/ScorePanel";
import Timeline from "../components/Timeline";
import DetailsDrawer from "../components/DetailsDrawer";
import "./Dashboard.css";

const POLL_INTERVAL_MS = 3000;

export default function Dashboard() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [scans, setScans] = useState<Scan[]>([]);
  const [activeScan, setActiveScan] = useState<Scan | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [loadingScans, setLoadingScans] = useState(true);
  const [loadingFindings, setLoadingFindings] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sseCleanupRef = useRef<(() => void) | null>(null);

  // ---------------------------------------------------------------- load scans

  const loadScans = useCallback(async () => {
    try {
      const data = await listScans();
      setScans(data);
      return data;
    } catch (e) {
      setError(String(e));
      return [];
    } finally {
      setLoadingScans(false);
    }
  }, []);

  // ---------------------------------------------------------------- select scan

  const selectScan = useCallback(async (scan: Scan) => {
    setActiveScan(scan);
    setEvents([]);
    setFindings([]);

    // If completed fetch findings now
    if (scan.status === "completed") {
      setLoadingFindings(true);
      try {
        const page = await getFindings(scan.scan_id, { page_size: 200 });
        setFindings(page.findings);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoadingFindings(false);
      }
    }
  }, []);

  // ---------------------------------------------------------------- SSE + polling

  const startLiveTracking = useCallback(
    (scan: Scan) => {
      // Clean up any existing SSE / poll
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
        sseCleanupRef.current = null;
      }
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }

      if (scan.status !== "running" && scan.status !== "pending") return;

      // Fetch any events emitted before we connected, then open live SSE
      getAgentEventHistory(scan.scan_id).then((history) => {
        if (history.length > 0) {
          setEvents(history);
        }

        // Subscribe SSE events (only new events after history)
        sseCleanupRef.current = subscribeAgentEvents(
          scan.scan_id,
          (ev) => setEvents((prev) => [...prev, ev]),
          async () => {
            // Stream done → fetch final state
            try {
              const final = await getScan(scan.scan_id);
              setActiveScan(final);
              const page = await getFindings(final.scan_id, { page_size: 200 });
              setFindings(page.findings);
              setScans((prev) =>
                prev.map((s) => (s.scan_id === final.scan_id ? final : s))
              );
            } catch (e) {
              setError(String(e));
            }
          }
        );

        // Poll status every 3 s for progress bar accuracy
        pollRef.current = setInterval(async () => {
          try {
            const updated = await getScan(scan.scan_id);
            setActiveScan(updated);
            setScans((prev) =>
              prev.map((s) => (s.scan_id === updated.scan_id ? updated : s))
            );
            if (updated.status !== "running" && updated.status !== "pending") {
              clearInterval(pollRef.current!);
              pollRef.current = null;
            }
          } catch (e) {
            /* ignore polling errors */
          }
        }, POLL_INTERVAL_MS);
      });
    },
    []
  );

  // ---------------------------------------------------------------- initial load

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const data = await loadScans();
      if (cancelled || data.length === 0) return;

      // Prefer scan_id from URL params
      const urlScanId = searchParams.get("scan_id");
      const target =
        (urlScanId && data.find((s) => s.scan_id === urlScanId)) || data[0];

      if (target) {
        await selectScan(target);
        if (target.status === "running" || target.status === "pending") {
          startLiveTracking(target);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------- cleanup

  useEffect(() => {
    return () => {
      if (sseCleanupRef.current) sseCleanupRef.current();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // ---------------------------------------------------------------- handlers

  const handleScanSelect = async (scan: Scan) => {
    await selectScan(scan);
    if (scan.status === "running" || scan.status === "pending") {
      startLiveTracking(scan);
    }
  };

  const handleCancelScan = async () => {
    if (!activeScan) return;
    try {
      await cancelScan(activeScan.scan_id);
      const updated = await getScan(activeScan.scan_id);
      setActiveScan(updated);
      setScans((prev) =>
        prev.map((s) => (s.scan_id === updated.scan_id ? updated : s))
      );
    } catch (e) {
      setError(String(e));
    }
  };

  const handleRerunScan = async () => {
    if (!activeScan) return;
    try {
      const newScan = await rerunScan(activeScan.scan_id);
      setScans((prev) => [newScan, ...prev]);
      await selectScan(newScan);
      startLiveTracking(newScan);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleShareLink = () => {
    if (!activeScan) return;
    const url = `${window.location.origin}/?scan_id=${activeScan.scan_id}`;
    navigator.clipboard.writeText(url).then(
      () => setCopied(true),
      () => setError("Failed to copy link")
    );
    setTimeout(() => setCopied(false), 2000);
  };

  const [copied, setCopied] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [reportData, setReportData] = useState<Record<string, unknown> | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "timeline">("table");
  const [timelineFinding, setTimelineFinding] = useState<Finding | null>(null);

  const handleViewReport = async () => {
    if (!activeScan) return;
    try {
      const report = await getExecutiveReport(activeScan.scan_id);
      setReportData(report);
      setShowReport(true);
    } catch (e) {
      setError(String(e));
    }
  };

  // ---------------------------------------------------------------- empty state

  if (!loadingScans && scans.length === 0) {
    return (
      <main className="dashboard dashboard--empty">
        <div className="empty-state">
          <div className="empty-icon">⚡</div>
          <h2>No scans yet</h2>
          <p>Run your first regulatory diligence scan to get started.</p>
          <button
            className="primary-btn"
            onClick={() => navigate("/new-scan")}
            type="button"
          >
            ▶ Run New Scan
          </button>
        </div>
      </main>
    );
  }

  // ---------------------------------------------------------------- render

  return (
    <main className="dashboard">
      {error && (
        <div className="error-banner" role="alert">
          {error}{" "}
          <button onClick={() => setError(null)} type="button">
            ✕
          </button>
        </div>
      )}

      {/* Scan selector sidebar */}
      {scans.length > 1 && (
        <aside className="scan-list">
          <div className="scan-list-header">Scans</div>
          {scans.map((s) => (
            <button
              key={s.scan_id}
              type="button"
              className={`scan-list-item ${
                activeScan?.scan_id === s.scan_id ? "scan-list-item--active" : ""
              }`}
              onClick={() => handleScanSelect(s)}
            >
              <span className={`status-dot status-dot--${s.status}`} />
              <span className="scan-list-target">{s.target}</span>
              <span className="scan-list-status">{s.status}</span>
            </button>
          ))}
        </aside>
      )}

      <div className="dashboard-content">
        {activeScan ? (
          <>
            <ContextStrip scan={activeScan} />

            <div className="dashboard-body">
              {/* Left column: score + actions */}
              <div className="dashboard-left">
                <ScorePanel scan={activeScan} findings={findings} />

                <div className="scan-actions">
                  {(activeScan.status === "running" ||
                    activeScan.status === "pending") && (
                    <button
                      className="cancel-btn"
                      onClick={handleCancelScan}
                      type="button"
                    >
                      ✕ Cancel Scan
                    </button>
                  )}

                  {activeScan.status === "completed" && (
                    <>
                      <button
                        className="action-btn action-btn--rerun"
                        onClick={handleRerunScan}
                        type="button"
                        title="Re-run this scan with the same parameters"
                      >
                        🔄 Re-run
                      </button>
                      <button
                        className="action-btn action-btn--report"
                        onClick={handleViewReport}
                        type="button"
                        title="Generate executive diligence report"
                      >
                        📋 Report
                      </button>
                    </>
                  )}

                  <button
                    className="action-btn action-btn--share"
                    onClick={handleShareLink}
                    type="button"
                    title="Copy shareable link"
                  >
                    {copied ? "✓ Copied!" : "🔗 Share"}
                  </button>
                </div>
              </div>

              {/* Right column: side-by-side agent cards (browser + log each) + findings */}
              <div className="dashboard-right">
                <BrowserGrid
                  events={events}
                  scan={activeScan}
                  scanRunning={
                    activeScan.status === "running" ||
                    activeScan.status === "pending"
                  }
                />
                <div className="view-toggle">
                  <button
                    className={`view-toggle-btn ${viewMode === "table" ? "view-toggle-btn--active" : ""}`}
                    onClick={() => setViewMode("table")}
                    type="button"
                  >
                    Table
                  </button>
                  <button
                    className={`view-toggle-btn ${viewMode === "timeline" ? "view-toggle-btn--active" : ""}`}
                    onClick={() => setViewMode("timeline")}
                    type="button"
                  >
                    Timeline
                  </button>
                </div>

                {viewMode === "table" ? (
                  <FindingsTable
                    findings={findings}
                    loading={loadingFindings}
                    scanId={activeScan.scan_id}
                  />
                ) : (
                  <Timeline
                    findings={findings}
                    onSelect={(f) => setTimelineFinding(f)}
                  />
                )}

                {timelineFinding && (
                  <DetailsDrawer
                    finding={timelineFinding}
                    onClose={() => setTimelineFinding(null)}
                  />
                )}
              </div>
            </div>

            {/* Executive report modal */}
            {showReport && reportData && (
              <>
                <div className="report-overlay" onClick={() => setShowReport(false)} />
                <div className="report-modal">
                  <div className="report-header">
                    <h3>{reportData.title as string}</h3>
                    <button
                      className="drawer-close"
                      onClick={() => setShowReport(false)}
                      type="button"
                    >
                      ✕
                    </button>
                  </div>
                  <p className="report-subtitle">{reportData.subtitle as string}</p>

                  <div className="report-section">
                    <h4>Executive Summary</h4>
                    <p>{reportData.executive_summary as string}</p>
                  </div>

                  {(reportData.key_metrics as Record<string, unknown>) && (
                    <div className="report-section">
                      <h4>Key Metrics</h4>
                      <div className="report-metrics-grid">
                        {Object.entries(reportData.key_metrics as Record<string, unknown>).map(
                          ([key, val]) => (
                            <div key={key} className="report-metric">
                              <span className="report-metric-label">
                                {key.replace(/_/g, " ")}
                              </span>
                              <span className="report-metric-value">{String(val)}</span>
                            </div>
                          )
                        )}
                      </div>
                    </div>
                  )}

                  {Array.isArray(reportData.recommendations) &&
                    (reportData.recommendations as string[]).length > 0 && (
                      <div className="report-section">
                        <h4>Recommendations</h4>
                        <ul className="report-recs">
                          {(reportData.recommendations as string[]).map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                  {Array.isArray(reportData.source_breakdown) &&
                    (reportData.source_breakdown as Array<Record<string, unknown>>).length > 0 && (
                      <div className="report-section">
                        <h4>Source Breakdown</h4>
                        <table className="report-table">
                          <thead>
                            <tr>
                              <th>Source</th>
                              <th>Findings</th>
                              <th>Exposure</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(reportData.source_breakdown as Array<Record<string, unknown>>).map((sb) => (
                              <tr key={sb.source_id as string}>
                                <td>{sb.source_id as string}</td>
                                <td>{String(sb.findings_count)}</td>
                                <td>{sb.exposure as string}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                </div>
              </>
            )}
          </>
        ) : (
          loadingScans && (
            <div className="loading-state">
              <div className="spinner" />
              <p>Loading scans…</p>
            </div>
          )
        )}
      </div>
    </main>
  );
}
