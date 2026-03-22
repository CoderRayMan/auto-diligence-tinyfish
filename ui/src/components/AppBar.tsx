import React from "react";
import { Link, useNavigate } from "react-router-dom";
import "./AppBar.css";

interface Props {
  agentCount?: number;
  connected?: boolean;
}

export default function AppBar({ agentCount = 0, connected = true }: Props) {
  const navigate = useNavigate();

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
        <span className="badge">v0.1 · Sandbox</span>
      </div>

      <div className="app-bar-right">
        <div className="status-line">
          <span
            className={`status-dot ${connected ? "status-dot--connected" : "status-dot--disconnected"}`}
          />
          <span>
            {connected
              ? `Connected to TinyFish · ${agentCount} agents idle`
              : "Disconnected"}
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
