import React, { useEffect, useRef } from "react";
import type { AgentEvent } from "../api/types";
import "./AgentLog.css";

interface Props {
  events: AgentEvent[];
  scanRunning: boolean;
}

const TAG_CLASS: Record<string, string> = {
  RUNNING: "tag--running",
  COMPLETED: "tag--completed",
  WAITING: "tag--waiting",
  FAILED: "tag--failed",
};

export default function AgentLog({ events, scanRunning }: Props) {
  const bottomRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <section className="agent-log-panel">
      <div className="section-header">
        <span>Agent activity (TinyFish)</span>
        {scanRunning && (
          <span className="log-live-badge">● LIVE</span>
        )}
      </div>

      {events.length === 0 ? (
        <div className="log-empty">No agent activity yet.</div>
      ) : (
        <ul className="log-list">
          {events.map((ev, i) => (
            <li
              key={i}
              className="log-item"
              ref={i === events.length - 1 ? bottomRef : undefined}
            >
              <div className="log-meta">
                <span className="log-source">{ev.source_id}</span>
                <span className={`log-tag ${TAG_CLASS[ev.agent_tag] ?? ""}`}>
                  {ev.agent_tag}
                </span>
                <span className="log-time">
                  {new Date(ev.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div className="log-body">{ev.message}</div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
