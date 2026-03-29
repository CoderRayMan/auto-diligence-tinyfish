import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Plus,
  RefreshCw,
  FileText,
  Bookmark,
  Link2,
  X,
  ChevronLeft,
  ClipboardList,
  Bot,
  SearchIcon,
  Zap,
  Download,
  BarChart2,
  List,
  GitBranch,
  AlertTriangle,
  TrendingUp,
  Building2,
  Activity,
  ShieldAlert,
  Pin,
  Scale,
  Keyboard,
} from "lucide-react";
import type { AgentEvent, Finding, RiskTrendPoint, Scan } from "../api/types";
import {
  cancelScan,
  getAgentEventHistory,
  getFindings,
  getScan,
  listScans,
  subscribeAgentEvents,
  rerunScan,
  getExecutiveReport,
  getRiskTrend,
  addToWatchlist,
  downloadFindingsCSV,
} from "../api/client";
import BrowserGrid from "../components/BrowserGrid";
import ContextStrip from "../components/ContextStrip";
import FindingsTable from "../components/FindingsTable";
import ScorePanel from "../components/ScorePanel";
import Timeline from "../components/Timeline";
import DetailsDrawer from "../components/DetailsDrawer";
import WatchlistPanel from "../components/WatchlistPanel";
import CompareModal from "../components/CompareModal";
import RiskSparkline from "../components/RiskSparkline";
import KeyboardShortcutsModal from "../components/KeyboardShortcutsModal";
import DigestPanel from "../components/DigestPanel";
import RunAuditPanel from "../components/RunAuditPanel";
import SchedulerWidget from "../components/SchedulerWidget";
import { useToast } from "../components/ToastContainer";
import "./Dashboard.css";

const POLL_INTERVAL_MS = 3000;

export default function Dashboard() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { toast } = useToast();

  const [scans, setScans] = useState<Scan[]>([]);
  const [activeScan, setActiveScan] = useState<Scan | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [loadingScans, setLoadingScans] = useState(true);
  const [loadingFindings, setLoadingFindings] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [copied, setCopied] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [reportData, setReportData] = useState<Record<string, unknown> | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "timeline">("table");
  const [timelineFinding, setTimelineFinding] = useState<Finding | null>(null);
  const [showWatchlist, setShowWatchlist] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [sparklines, setSparklines] = useState<Record<string, RiskTrendPoint[]>>({});
  const [homeTab, setHomeTab] = useState<"scans" | "digest" | "runs">("scans");

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
          (ev) =>
            setEvents((prev) => {
              // Deduplicate: the SSE queue replays history events, so skip any
              // event that's identical to one already captured from history.
              const isDup = prev.some(
                (e) =>
                  e.timestamp === ev.timestamp &&
                  e.source_id === ev.source_id &&
                  e.agent_tag === ev.agent_tag &&
                  e.message === ev.message
              );
              return isDup ? prev : [...prev, ev];
            }),
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
              // Safety fallback: if SSE "done" was missed, fetch findings now
              if (updated.status === "completed") {
                setFindings((prev) => {
                  if (prev.length === 0) {
                    getFindings(updated.scan_id, { page_size: 200 })
                      .then((page) => setFindings(page.findings))
                      .catch(() => {});
                  }
                  return prev;
                });
              }
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

      // Only auto-select if scan_id is in URL; otherwise show home grid
      const urlScanId = searchParams.get("scan_id");
      if (urlScanId) {
        const target = data.find((s) => s.scan_id === urlScanId);
        if (target) {
          await selectScan(target);
          if (target.status === "running" || target.status === "pending") {
            startLiveTracking(target);
          }
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

  const handleRerunScan = async () => {
    if (!activeScan) return;
    try {
      const newScan = await rerunScan(activeScan.scan_id);
      setScans((prev) => [newScan, ...prev]);
      await selectScan(newScan);
      startLiveTracking(newScan);
      toast(`Re-run started for "${newScan.target}"`, "success");
    } catch (e) {
      toast(String(e), "error");
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
      toast("Scan cancelled", "info");
    } catch (e) {
      toast(String(e), "error");
    }
  };

  const handleBackToHome = () => {
    setActiveScan(null);
    setFindings([]);
    setEvents([]);
    if (sseCleanupRef.current) { sseCleanupRef.current(); sseCleanupRef.current = null; }
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const handleShareLink = () => {
    if (!activeScan) return;
    const url = `${window.location.origin}/?scan_id=${activeScan.scan_id}`;
    navigator.clipboard.writeText(url).then(
      () => { setCopied(true); toast("Link copied to clipboard", "success"); },
      () => toast("Failed to copy link", "error")
    );
    setTimeout(() => setCopied(false), 2000);
  };

  const handleViewReport = async () => {
    if (!activeScan) return;
    try {
      const report = await getExecutiveReport(activeScan.scan_id);
      setReportData(report);
      setShowReport(true);
    } catch (e) {
      toast(String(e), "error");
    }
  };

  const handleAddToWatchlist = async () => {
    if (!activeScan) return;
    try {
      await addToWatchlist(activeScan.target, activeScan.persona_id ?? undefined);
      toast(`"${activeScan.target}" added to watchlist`, "success");
    } catch (e) {
      const msg = String(e);
      toast(msg.includes("409") ? "Already in watchlist" : msg, "warning");
    }
  };

  const handleRerunScanWithToast = handleRerunScan;

  // Load sparklines for home grid (all completed scans, batch)
  useEffect(() => {
    const completedTargets = [...new Set(
      scans.filter((s) => s.status === "completed").map((s) => s.target)
    )];
    completedTargets.forEach(async (target) => {
      if (sparklines[target]) return; // already loaded
      try {
        const trend = await getRiskTrend(target, 8);
        if (trend.data_points.length >= 2) {
          setSparklines((prev) => ({ ...prev, [target]: trend.data_points }));
        }
      } catch {
        // no trend yet — only 1 scan for this entity
      }
    });
  }, [scans]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      switch (e.key) {
        case "n": case "N": navigate("/new-scan"); break;
        case "d": case "D": handleBackToHome(); break;
        case "w": case "W": setShowWatchlist((v) => !v); break;
        case "c": case "C": if (scans.filter(s => s.status === "completed").length >= 2) setShowCompare(true); break;
        case "?": setShowShortcuts((v) => !v); break;
        case "r": case "R": if (activeScan?.status === "completed") handleRerunScan(); break;
        case "e": case "E": if (activeScan && findings.length > 0) downloadFindingsCSV(activeScan.scan_id); break;
        case "p": case "P": if (activeScan?.status === "completed") handleViewReport(); break;
        case "t": case "T": setViewMode((v) => v === "table" ? "timeline" : "table"); break;
        case "Escape":
          setShowReport(false);
          setShowCompare(false);
          setShowShortcuts(false);
          setShowWatchlist(false);
          setTimelineFinding(null);
          break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [activeScan, findings, scans]); // eslint-disable-line react-hooks/exhaustive-deps

  // Scan progress percentage
  const progressPct = activeScan
    ? activeScan.sources_total > 0
      ? Math.round(((activeScan.sources_completed + activeScan.sources_failed) / activeScan.sources_total) * 100)
      : 0
    : 0;

  // ---------------------------------------------------------------- helpers

  const riskColor = (label: string | undefined) => {
    switch ((label ?? "").toLowerCase()) {
      case "critical": return "#f87171";
      case "high":     return "#fb923c";
      case "medium":   return "#fbbf24";
      case "low":      return "#4ade80";
      default:         return "#94a3b8";
    }
  };

  const formatDate = (iso: string | undefined) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  };

  // ---------------------------------------------------------------- empty state

  if (!loadingScans && scans.length === 0) {
    return (
      <main className="dashboard dashboard--empty">
        <div className="empty-state">
          <div className="empty-icon"><Zap size={26} /></div>
          <h2>No scans yet</h2>
          <p>Run your first regulatory diligence scan to get started.</p>
          <button
            className="primary-btn"
            onClick={() => navigate("/new-scan")}
            type="button"
          >
            <Plus size={15} /> New Scan
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
          <AlertTriangle size={14} />{error}{" "}
          <button onClick={() => setError(null)} type="button" aria-label="Dismiss">
            <X size={13} />
          </button>
        </div>
      )}

      {/* Scan selector sidebar — only visible when a scan is open */}
      {activeScan && scans.length > 1 && (
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
        {/* ── Home grid: completed scans overview ─────────────────── */}
        {!activeScan && !loadingScans && (
          <div className="scans-home">
            <div className="scans-home-header">
              <div>
                <h2 className="scans-home-title">AutoDiligence</h2>
                <p className="scans-home-sub">
                  {scans.filter((s) => s.status === "completed").length} completed ·{" "}
                  {scans.filter((s) => s.status === "running").length} running
                </p>
              </div>
              <div className="scans-home-actions">
                <SchedulerWidget />
                <button
                  className="primary-btn"
                  onClick={() => navigate("/new-scan")}
                  type="button"
                >
                  <Plus size={14} /> New Scan
                </button>
              </div>
            </div>

            {/* ── KPI stats row ─────────────────────────────────── */}
            {homeTab === "scans" && scans.length > 0 && (() => {
              const completed = scans.filter(s => s.status === "completed");
              const running = scans.filter(s => s.status === "running" || s.status === "pending");
              const critical = completed.filter(s => (s.risk_label ?? "").toLowerCase() === "critical").length;
              const entities = new Set(completed.map(s => s.target)).size;
              const totalFindings = completed.reduce((sum, s) => sum + (s.findings_count ?? 0), 0);
              return (
                <div className="kpi-row">
                  <div className="kpi-card">
                    <div className="kpi-icon kpi-icon--accent"><Building2 size={16} /></div>
                    <div className="kpi-body">
                      <div className="kpi-value">{entities}</div>
                      <div className="kpi-label">Entities Monitored</div>
                    </div>
                  </div>
                  <div className="kpi-card">
                    <div className="kpi-icon kpi-icon--success"><ClipboardList size={16} /></div>
                    <div className="kpi-body">
                      <div className="kpi-value">{completed.length}</div>
                      <div className="kpi-label">Completed Scans</div>
                    </div>
                  </div>
                  <div className={`kpi-card${critical > 0 ? " kpi-card--danger" : ""}`}>
                    <div className={`kpi-icon${critical > 0 ? " kpi-icon--danger" : " kpi-icon--muted"}`}><ShieldAlert size={16} /></div>
                    <div className="kpi-body">
                      <div className="kpi-value">{critical}</div>
                      <div className="kpi-label">Critical Risk</div>
                    </div>
                  </div>
                  <div className="kpi-card">
                    <div className="kpi-icon kpi-icon--warning"><TrendingUp size={16} /></div>
                    <div className="kpi-body">
                      <div className="kpi-value">{totalFindings}</div>
                      <div className="kpi-label">Total Findings</div>
                    </div>
                  </div>
                  {running.length > 0 && (
                    <div className="kpi-card kpi-card--running">
                      <div className="kpi-icon kpi-icon--running"><Activity size={16} /></div>
                      <div className="kpi-body">
                        <div className="kpi-value">{running.length}</div>
                        <div className="kpi-label">Running Now</div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Home tabs */}
            <div className="home-tabs">
              <button
                className={`home-tab ${homeTab === "scans" ? "home-tab--active" : ""}`}
                onClick={() => setHomeTab("scans")}
              >
                <ClipboardList size={14} /> Scans
              </button>
              <button
                className={`home-tab ${homeTab === "digest" ? "home-tab--active" : ""}`}
                onClick={() => setHomeTab("digest")}
              >
                <Bot size={14} /> AI Briefings
              </button>
              <button
                className={`home-tab ${homeTab === "runs" ? "home-tab--active" : ""}`}
                onClick={() => setHomeTab("runs")}
              >
                <SearchIcon size={14} /> Run Audit
              </button>
            </div>

            {/* Scans tab */}
            {homeTab === "scans" && (
              <>
            {scans.filter((s) => s.status === "completed").length === 0 ? (
              <div className="scans-home-empty">
                <div className="empty-icon"><ClipboardList size={22} /></div>
                <p>No completed scans yet.</p>
              </div>
            ) : (
              <div className="scan-cards-grid">
                {scans
                  .filter((s) => s.status === "completed")
                  .map((s, idx) => (
                    <button
                      key={s.scan_id}
                      type="button"
                      className={`scan-card scan-card--risk-${(s.risk_label ?? "none").toLowerCase()} animate-up`}
                      style={{ animationDelay: `${idx * 45}ms` }}
                      onClick={() => handleScanSelect(s)}
                    >
                      <div className="scan-card-risk-bar" style={{ background: riskColor(s.risk_label) }} />
                      <div className="scan-card-top">
                        <span
                          className="scan-card-risk-badge"
                          style={{ borderColor: riskColor(s.risk_label), color: riskColor(s.risk_label) }}
                        >
                          {s.risk_label ?? "—"}
                        </span>
                        <span className="scan-card-score" style={{ color: riskColor(s.risk_label) }}>
                          {s.risk_score != null ? s.risk_score : "—"}
                          <span className="scan-card-score-unit">/100</span>
                        </span>
                      </div>

                      <div className="scan-card-target">{s.target}</div>
                      <div className="scan-card-query">{s.query}</div>

                      <div className="scan-card-meta">
                        <span className="scan-card-findings">
                          {s.findings_count ?? 0} finding{(s.findings_count ?? 0) !== 1 ? "s" : ""}
                        </span>
                        <span className="scan-card-date">{formatDate(s.created_at)}</span>
                      </div>

                      {s.source_results && s.source_results.length > 0 && (
                        <div className="scan-card-source-chips">
                          {s.source_results.map((sr) => (
                            <span
                              key={sr.source_id}
                              className={`source-mini-chip source-mini-chip--${sr.status}`}
                              title={`${sr.source_id.toUpperCase()}: ${sr.records_found} records`}
                            >
                              {sr.source_id.replace("us_", "").toUpperCase()}
                            </span>
                          ))}
                        </div>
                      )}

                      <div className="scan-card-footer">
                        <span className="scan-card-sources">
                          {s.sources_completed ?? 0}/{s.sources_total ?? 0} sources
                        </span>
                        {sparklines[s.target] && (
                          <RiskSparkline points={sparklines[s.target]} />
                        )}
                        <span className="scan-card-cta">View Details →</span>
                      </div>
                    </button>
                  ))}
              </div>
            )}

            {/* Non-completed scans (running/pending/failed) */}
            {scans.filter((s) => s.status !== "completed").length > 0 && (
              <div className="scans-home-section">
                <h3 className="scans-home-section-title">Active &amp; Other Scans</h3>
                <div className="scan-cards-grid">
                  {scans
                    .filter((s) => s.status !== "completed")
                    .map((s) => (
                      <button
                        key={s.scan_id}
                        type="button"
                        className="scan-card scan-card--active"
                        onClick={() => handleScanSelect(s)}
                      >
                        <div className="scan-card-top">
                          <span className={`status-dot status-dot--${s.status}`} />
                          <span className="scan-card-status-label">{s.status}</span>
                        </div>
                        <div className="scan-card-target">{s.target}</div>
                        <div className="scan-card-meta">
                          <span className="scan-card-date">{formatDate(s.created_at)}</span>
                        </div>
                        <div className="scan-card-footer">
                          <span className="scan-card-cta">Open →</span>
                        </div>
                      </button>
                    ))}
                </div>
              </div>
            )}
            </>
            )}

            {/* AI Briefings tab */}
            {homeTab === "digest" && (
              <DigestPanel
                scannedTargets={[
                  ...new Set(
                    scans
                      .filter((s) => s.status === "completed")
                      .map((s) => s.target)
                  ),
                ]}
              />
            )}

            {/* Run Audit tab */}
            {homeTab === "runs" && (
              <div style={{ height: "720px" }}>
                <RunAuditPanel />
              </div>
            )}
          </div>
        )}

        {activeScan ? (
          <>
            <div className="dashboard-breadcrumb">
              <button type="button" className="breadcrumb-back" onClick={handleBackToHome}>
                <ChevronLeft size={13} /> All Scans
              </button>
              <span className="breadcrumb-sep">/</span>
              <span className="breadcrumb-current">{activeScan.target}</span>
            </div>
            <ContextStrip scan={activeScan} />

            <div className="dashboard-body">
              {/* Left column: score + actions */}
              <div className="dashboard-left">
                <ScorePanel scan={activeScan} findings={findings} />

                <div className="scan-actions">
                  {(activeScan.status === "running" ||
                    activeScan.status === "pending") && (
                    <>
                      {/* Progress bar */}
                      <div className="scan-progress-bar-wrap">
                        <div
                          className="scan-progress-bar"
                          style={{ width: `${progressPct}%` }}
                        />
                        <span className="scan-progress-label">
                          {activeScan.sources_completed + activeScan.sources_failed}/{activeScan.sources_total} sources · {progressPct}%
                        </span>
                      </div>
                      <button
                        className="cancel-btn"
                        onClick={handleCancelScan}
                        type="button"
                      >
                        <X size={13} /> Cancel Scan
                      </button>
                    </>
                  )}

                  {activeScan.status === "completed" && (
                    <>
                      <button
                        className="action-btn action-btn--rerun"
                        onClick={handleRerunScan}
                        type="button"
                        title="Re-run this scan [R]"
                      >
                        <RefreshCw size={13} /> Re-run
                      </button>
                      <button
                        className="action-btn action-btn--report"
                        onClick={handleViewReport}
                        type="button"
                        title="Executive report [P]"
                      >
                        <FileText size={13} /> Report
                      </button>
                      <button
                        className="action-btn action-btn--watchlist"
                        onClick={handleAddToWatchlist}
                        type="button"
                        title="Pin to watchlist"
                      >
                        <Bookmark size={13} /> Watch
                      </button>
                    </>
                  )}

                  <button
                    className="action-btn action-btn--share"
                    onClick={handleShareLink}
                    type="button"
                    title="Copy shareable link"
                  >
                    <Link2 size={13} /> {copied ? "Copied!" : "Share"}
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
                    <List size={13} /> Table
                  </button>
                  <button
                    className={`view-toggle-btn ${viewMode === "timeline" ? "view-toggle-btn--active" : ""}`}
                    onClick={() => setViewMode("timeline")}
                    type="button"
                  >
                    <GitBranch size={13} /> Timeline
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
                      aria-label="Close"
                    >
                      <X size={16} />
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

      {/* Watchlist side panel */}
      {showWatchlist && (
        <div className="watchlist-drawer">
          <div className="watchlist-drawer-header">
            <span>Watchlist</span>
            <button
              className="watchlist-drawer-close"
              type="button"
              onClick={() => setShowWatchlist(false)}
              aria-label="Close watchlist"
            >
              <X size={14} />
            </button>
          </div>
          <WatchlistPanel
            onSelectEntity={(name) => {
              setShowWatchlist(false);
              const scan = scans.find((s) => s.target.toLowerCase() === name.toLowerCase() && s.status === "completed");
              if (scan) handleScanSelect(scan);
            }}
          />
        </div>
      )}

      {/* Compare modal */}
      {showCompare && (
        <CompareModal
          scans={scans}
          defaultScanId={activeScan?.scan_id}
          onClose={() => setShowCompare(false)}
        />
      )}

      {/* Keyboard shortcuts modal */}
      {showShortcuts && (
        <KeyboardShortcutsModal onClose={() => setShowShortcuts(false)} />
      )}

      {/* Global toolbar (bottom-right) */}
      <div className="global-toolbar">
        <button
          className="global-btn"
          type="button"
          title="Watchlist [W]"
          onClick={() => setShowWatchlist((v) => !v)}
          aria-label="Toggle watchlist"
        >
          <Pin size={14} />
        </button>
        {scans.filter((s) => s.status === "completed").length >= 2 && (
          <button
            className="global-btn"
            type="button"
            title="Compare scans [C]"
            onClick={() => setShowCompare(true)}
            aria-label="Compare scans"
          >
            <Scale size={14} />
          </button>
        )}
        <button
          className="global-btn"
          type="button"
          title="Keyboard shortcuts [?]"
          onClick={() => setShowShortcuts((v) => !v)}
          aria-label="Keyboard shortcuts"
        >
          <Keyboard size={14} />
        </button>
      </div>
    </main>
  );
}
