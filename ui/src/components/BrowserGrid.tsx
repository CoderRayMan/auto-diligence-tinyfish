import React, { useEffect, useRef, useState } from "react";
import { ExternalLink } from "lucide-react";
import type { AgentEvent, Scan } from "../api/types";
import "./BrowserGrid.css";

interface Props {
  events: AgentEvent[];
  scan: Scan | null;
  scanRunning: boolean;
}

interface AgentSession {
  source_id: string;
  streaming_url: string;
  status: "pending" | "running" | "completed" | "failed";
}

const SOURCE_LABELS: Record<string, string> = {
  us_osha: "OSHA",
  us_fda: "FDA",
  us_sec: "SEC",
  us_dol: "DOL",
  us_epa: "EPA",
};

const TAG_CLASS: Record<string, string> = {
  RUNNING: "tag--running",
  COMPLETED: "tag--completed",
  FAILED: "tag--failed",
  STREAMING_URL: "tag--running",
  WAITING: "tag--waiting",
};

// ── Single agent card ──────────────────────────────────── //

function AgentCard({
  session,
  events,
  scanRunning,
}: {
  session: AgentSession;
  events: AgentEvent[];
  scanRunning: boolean;
}) {
  const [iframeBlocked, setIframeBlocked] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const blockedRef = useRef(false);
  const logRef = useRef<HTMLUListElement>(null);

  const myEvents = events.filter((e) => e.source_id === session.source_id);

  // Auto-scroll log to bottom on new events
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [myEvents.length]);

  const handleIframeRef = (el: HTMLIFrameElement | null) => {
    if (!el || blockedRef.current) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      blockedRef.current = true;
      setIframeBlocked(true);
    }, 8000);
  };

  const handleIframeLoad = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const label = SOURCE_LABELS[session.source_id] ?? session.source_id.toUpperCase();

  return (
    <div className={`agent-card agent-card--${session.status}`}>
      {/* Card header */}
      <div className="agent-card-header">
        <span className={`agent-card-dot dot--${session.status}`} />
        <span className="agent-card-name">{label}</span>
        <span className={`agent-card-badge badge--${session.status}`}>{session.status}</span>
        {session.streaming_url && (
          <a
            href={session.streaming_url}
            target="_blank"
            rel="noopener noreferrer"
            className="agent-card-popout"
            title="Open in new tab"
          >
            <ExternalLink size={14} aria-hidden />
          </a>
        )}
      </div>

      {/* Browser area */}
      <div className="agent-card-browser">
        {session.streaming_url && !iframeBlocked ? (
          <iframe
            key={session.streaming_url}
            className="agent-card-iframe"
            src={session.streaming_url}
            title={`Live — ${label}`}
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-pointer-lock allow-presentation"
            allow="clipboard-read; clipboard-write"
            referrerPolicy="no-referrer-when-downgrade"
            ref={handleIframeRef}
            onLoad={handleIframeLoad}
            onError={() => setIframeBlocked(true)}
          />
        ) : session.streaming_url && iframeBlocked ? (
          <div className="agent-card-noframe">
            <a
              href={session.streaming_url}
              target="_blank"
              rel="noopener noreferrer"
              className="open-stream-btn"
            >
              Open Live Browser <ExternalLink size={13} aria-hidden />
            </a>
          </div>
        ) : (
          <div className="agent-card-noframe">
            {scanRunning &&
              session.status !== "failed" &&
              session.status !== "completed" && (
                <div className="browser-waiting-spinner" />
              )}
            <p className="agent-card-wait-text">
              {session.status === "failed"
                ? "Agent failed"
                : session.status === "completed"
                ? "Completed - stream ended"
                : "Waiting for browser..."}
            </p>
          </div>
        )}
      </div>

      {/* Per-agent log */}
      <div className="agent-card-log">
        {myEvents.length === 0 ? (
          <div className="agent-card-log-empty">No activity yet</div>
        ) : (
          <ul className="agent-log-list" ref={logRef}>
            {myEvents.map((ev, i) => (
              <li key={i} className="agent-log-item">
                <span className={`agent-log-tag ${TAG_CLASS[ev.agent_tag] ?? ""}`}>
                  {ev.agent_tag}
                </span>
                <span className="agent-log-msg">{ev.message}</span>
                <span className="agent-log-time">
                  {new Date(ev.timestamp).toLocaleTimeString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── Grid wrapper ───────────────────────────────────────── //

export default function BrowserGrid({ events, scan, scanRunning }: Props) {
  // Build sessions map — seed from scan.source_results first, then overlay events
  const sessions: Record<string, AgentSession> = {};

  if (scan) {
    for (const sr of scan.source_results) {
      sessions[sr.source_id] = {
        source_id: sr.source_id,
        streaming_url: "",
        status:
          sr.status === "completed"
            ? "completed"
            : sr.status === "failed"
            ? "failed"
            : "pending",
      };
    }
  }

  for (const ev of events) {
    if (!sessions[ev.source_id]) {
      sessions[ev.source_id] = {
        source_id: ev.source_id,
        streaming_url: "",
        status: "pending",
      };
    }
    if (ev.agent_tag === "STREAMING_URL" && ev.streaming_url) {
      sessions[ev.source_id].streaming_url = ev.streaming_url;
    }
    if (ev.agent_tag === "RUNNING" || ev.agent_tag === "STREAMING_URL") {
      sessions[ev.source_id].status = "running";
    }
    if (ev.agent_tag === "COMPLETED") sessions[ev.source_id].status = "completed";
    if (ev.agent_tag === "FAILED") sessions[ev.source_id].status = "failed";
  }

  const list = Object.values(sessions);

  if (list.length === 0) {
    return (
      <section className="agent-grid-panel">
        <div className="agent-grid-header">
          <span>Live Agent Browsers</span>
        </div>
        <div className="agent-grid-empty">
          <p>No agents running. Start a scan to see live browsers and logs.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="agent-grid-panel">
      <div className="agent-grid-header">
        <span>Live Agent Browsers</span>
        {scanRunning && <span className="log-live-badge">● LIVE</span>}
      </div>
      <div className="agent-grid">
        {list.map((session) => (
          <AgentCard
            key={session.source_id}
            session={session}
            events={events}
            scanRunning={scanRunning}
          />
        ))}
      </div>
    </section>
  );
}
