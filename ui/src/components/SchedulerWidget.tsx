import React, { useEffect, useState } from "react";
import { getSchedulerStatus, triggerSchedulerSweep, pauseScheduler, resumeScheduler } from "../api/client";
import type { SchedulerStatus } from "../api/types";
import "./SchedulerWidget.css";

export const SchedulerWidget: React.FC = () => {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [countdown, setCountdown] = useState<string>("");

  const refresh = async () => {
    try {
      const s = await getSchedulerStatus();
      setStatus(s);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15_000);
    return () => clearInterval(id);
  }, []);

  // Countdown to next sweep
  useEffect(() => {
    if (!status?.next_sweep_at) { setCountdown(""); return; }
    const tick = () => {
      const diff = new Date(status.next_sweep_at!).getTime() - Date.now();
      if (diff <= 0) { setCountdown("soon"); return; }
      const m = Math.floor(diff / 60_000);
      const s = Math.floor((diff % 60_000) / 1000);
      setCountdown(`${m}m ${s}s`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [status?.next_sweep_at]);

  const handleTrigger = async () => {
    setLoading(true);
    try {
      await triggerSchedulerSweep();
      await refresh();
    } catch {/* ignore */}
    setLoading(false);
  };

  const handleTogglePause = async () => {
    setLoading(true);
    try {
      if (status?.paused) await resumeScheduler();
      else await pauseScheduler();
      await refresh();
    } catch {/* ignore */}
    setLoading(false);
  };

  if (!status) return null;

  const dot = status.running && !status.paused
    ? "scheduler-dot--running"
    : status.paused
      ? "scheduler-dot--paused"
      : "scheduler-dot--stopped";

  return (
    <div className="scheduler-widget">
      <button
        className="scheduler-pill"
        onClick={() => setExpanded(e => !e)}
        title="Proactive scheduler status"
      >
        <span className={`scheduler-dot ${dot}`} />
        <span className="scheduler-label">Auto-Scan</span>
        {countdown && status.running && !status.paused && (
          <span className="scheduler-countdown">{countdown}</span>
        )}
        {status.paused && <span className="scheduler-paused-label">PAUSED</span>}
      </button>

      {expanded && (
        <div className="scheduler-dropdown">
          <div className="scheduler-dropdown-header">
            <span>🔄 Proactive Re-scan Scheduler</span>
            <button className="scheduler-close" onClick={() => setExpanded(false)}>✕</button>
          </div>

          <div className="scheduler-stats-row">
            <div className="scheduler-stat">
              <span className="scheduler-stat-val">{status.sweep_count}</span>
              <span className="scheduler-stat-lbl">Sweeps</span>
            </div>
            <div className="scheduler-stat">
              <span className="scheduler-stat-val">{status.interval_minutes}m</span>
              <span className="scheduler-stat-lbl">Interval</span>
            </div>
            <div className="scheduler-stat">
              <span className="scheduler-stat-val">
                {status.recent_sweeps.reduce((a, s) => a + s.entities_queued, 0)}
              </span>
              <span className="scheduler-stat-lbl">Auto-queued</span>
            </div>
          </div>

          {status.last_sweep_at && (
            <div className="scheduler-time-row">
              <span className="scheduler-time-lbl">Last sweep</span>
              <span>{new Date(status.last_sweep_at).toLocaleTimeString()}</span>
            </div>
          )}
          {countdown && (
            <div className="scheduler-time-row">
              <span className="scheduler-time-lbl">Next sweep</span>
              <span className="scheduler-countdown-big">{countdown}</span>
            </div>
          )}

          {status.recent_sweeps.length > 0 && (
            <div className="scheduler-log">
              <div className="scheduler-log-lbl">Recent sweeps</div>
              {status.recent_sweeps.slice(0, 3).map((sw, i) => (
                <div key={i} className="scheduler-log-item">
                  <span>{new Date(sw.swept_at).toLocaleTimeString()}</span>
                  <span className="scheduler-log-queued">
                    {sw.entities_queued > 0
                      ? `+${sw.entities_queued} scan${sw.entities_queued !== 1 ? "s" : ""}`
                      : "no stale entities"}
                  </span>
                  {sw.triggered_manually && <span className="scheduler-manual-tag">manual</span>}
                </div>
              ))}
            </div>
          )}

          <div className="scheduler-actions">
            <button
              className="scheduler-btn scheduler-btn--trigger"
              onClick={handleTrigger}
              disabled={loading}
            >
              {loading ? "⏳" : "▶"} Sweep Now
            </button>
            <button
              className={`scheduler-btn ${status.paused ? "scheduler-btn--resume" : "scheduler-btn--pause"}`}
              onClick={handleTogglePause}
              disabled={loading}
            >
              {status.paused ? "▶ Resume" : "⏸ Pause"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SchedulerWidget;
