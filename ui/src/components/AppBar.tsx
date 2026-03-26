import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./AppBar.css";

interface Props {
  agentCount?: number;
  connected?: boolean;
}

export default function AppBar({ agentCount = 0 }: Props) {
  const navigate = useNavigate();
  const [apiOk, setApiOk] = useState<boolean | null>(null);

  // Check backend health on mount and every 30 s
  useEffect(() => {
    let cancelled = false;
    const check = () =>
      fetch("/api/health")
        .then((r) => { if (!cancelled) setApiOk(r.ok); })
        .catch(() => { if (!cancelled) setApiOk(false); });
    check();
    const id = setInterval(check, 30_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input or textarea
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (e.key === "n" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        navigate("/new-scan");
      }
      if (e.key === "d" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        navigate("/");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate]);

  const connected = apiOk === true;

  return (
    <header className="app-bar">
      <div className="app-bar-left">
        <Link to="/" className="logo-pill" aria-label="AutoDiligence home">
          A
        </Link>
        <div className="app-title">
          <h1>AutoDiligence</h1>
          <span>Regulatory Risk on TinyFish</span>
        </div>
        <span className="badge">v0.2 · Sandbox</span>
      </div>

      <div className="app-bar-right">
        <div className="kbd-hints">
          <kbd>N</kbd> New Scan
          <kbd>D</kbd> Dashboard
        </div>
        <div className="status-line">
          <span
            className={`status-dot ${
              apiOk === null
                ? ""
                : connected
                ? "status-dot--connected"
                : "status-dot--disconnected"
            }`}
          />
          <span>
            {apiOk === null
              ? "Checking..."
              : connected
              ? `API Online · ${agentCount} agents idle`
              : "API Offline"}
          </span>
        </div>
        <button
          className="primary-btn"
          onClick={() => navigate("/new-scan")}
          type="button"
        >
          <span className="icon" aria-hidden>▶</span>
          <span>Run New Scan</span>
        </button>
      </div>
    </header>
  );
}
