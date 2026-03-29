import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  ShieldCheck,
  LayoutDashboard,
  Plus,
  Wifi,
  WifiOff,
  Keyboard,
} from "lucide-react";
import { checkHealth } from "../api/client";
import "./AppBar.css";

interface Props {
  agentCount?: number;
  connected?: boolean;
}

export default function AppBar({ agentCount = 0 }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [showHint, setShowHint] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const check = () =>
      checkHealth()
        .then((ok) => { if (!cancelled) setApiOk(ok); })
        .catch(() => { if (!cancelled) setApiOk(false); });
    check();
    const id = setInterval(check, 30_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "n" && !e.ctrlKey && !e.metaKey) { e.preventDefault(); navigate("/new-scan"); }
      if (e.key === "d" && !e.ctrlKey && !e.metaKey) { e.preventDefault(); navigate("/"); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate]);

  const connected = apiOk === true;
  const isDashboard = location.pathname === "/";
  const isNewScan = location.pathname === "/new-scan";

  return (
    <header className="app-bar">
      <div className="app-bar-left">
        <Link to="/" className="logo-pill" aria-label="AutoDiligence home">
          <ShieldCheck size={17} strokeWidth={2.2} />
        </Link>
        <div className="app-title">
          <h1>AutoDiligence</h1>
          <span>Regulatory Intelligence</span>
        </div>
        <span className="env-badge">Enterprise</span>
      </div>

      <nav className="app-nav">
        <Link
          to="/"
          className={`nav-link ${isDashboard ? "nav-link--active" : ""}`}
        >
          <LayoutDashboard size={15} strokeWidth={1.8} />
          Dashboard
        </Link>
        <Link
          to="/new-scan"
          className={`nav-link nav-link--cta ${isNewScan ? "nav-link--active" : ""}`}
        >
          <Plus size={15} strokeWidth={2.2} />
          New Scan
        </Link>
      </nav>

      <div className="app-bar-right">
        <button
          className="kbd-hint-btn"
          title="Keyboard shortcuts (?)"
          onClick={() => setShowHint((v) => !v)}
          type="button"
        >
          <Keyboard size={14} />
        </button>
        {showHint && (
          <div className="kbd-tooltip">
            <div className="kbd-row"><kbd>N</kbd> New scan</div>
            <div className="kbd-row"><kbd>D</kbd> Dashboard</div>
            <div className="kbd-row"><kbd>W</kbd> Watchlist</div>
            <div className="kbd-row"><kbd>R</kbd> Re-run</div>
            <div className="kbd-row"><kbd>P</kbd> Report</div>
            <div className="kbd-row"><kbd>E</kbd> Export CSV</div>
            <div className="kbd-row"><kbd>T</kbd> Toggle view</div>
            <div className="kbd-row"><kbd>?</kbd> Shortcuts modal</div>
          </div>
        )}
        <div
          className={`api-status ${connected ? "api-status--ok" : apiOk === false ? "api-status--err" : "api-status--unknown"}`}
          title={connected ? "API connected · localhost:8000" : apiOk === false ? "API offline" : "Checking…"}
        >
          {connected
            ? <><Wifi size={13} /><span>Connected</span></>
            : apiOk === false
            ? <><WifiOff size={13} /><span>Offline</span></>
            : <span>…</span>
          }
        </div>
      </div>
    </header>
  );
}
