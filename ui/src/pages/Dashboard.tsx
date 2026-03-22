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
} from "../api/client";
import BrowserGrid from "../components/BrowserGrid";
import ContextStrip from "../components/ContextStrip";
import FindingsTable from "../components/FindingsTable";
import ScorePanel from "../components/ScorePanel";
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
              {/* Left column: score + cancel */}
              <div className="dashboard-left">
                <ScorePanel scan={activeScan} />
                {(activeScan.status === "running" ||
                  activeScan.status === "pending") && (
                  <button
                    className="cancel-btn"
                    onClick={handleCancelScan}
                    type="button"
                  >
                    Cancel Scan
                  </button>
                )}
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
                <FindingsTable
                  findings={findings}
                  loading={loadingFindings}
                />
              </div>
            </div>
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
