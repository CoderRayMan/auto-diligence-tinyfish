import React, { useCallback, useEffect, useState } from "react";
import type { WatchlistEntry } from "../api/types";
import {
  addToWatchlist,
  listWatchlist,
  removeFromWatchlist,
} from "../api/client";
import { useToast } from "./ToastContainer";
import "./WatchlistPanel.css";

interface Props {
  onSelectEntity?: (name: string) => void;
}

const RISK_COLOR: Record<string, string> = {
  critical: "#f87171",
  high: "#fb923c",
  medium: "#fbbf24",
  low: "#4ade80",
  Clean: "#4ade80",
};

function timeAgo(iso: string | undefined): string {
  if (!iso) return "Never scanned";
  const ms = Date.now() - new Date(iso).getTime();
  const d = Math.floor(ms / 86_400_000);
  const h = Math.floor(ms / 3_600_000);
  if (d > 0) return `${d}d ago`;
  if (h > 0) return `${h}h ago`;
  return "Just now";
}

export default function WatchlistPanel({ onSelectEntity }: Props) {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEntries(await listWatchlist());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      const entry = await addToWatchlist(newName.trim());
      setEntries((prev) => [...prev, entry]);
      setNewName("");
      setAdding(false);
      toast(`"${entry.entity_name}" added to watchlist`, "success");
    } catch (err) {
      toast(String(err).includes("409") ? "Already in watchlist" : String(err), "error");
    }
  };

  const handleRemove = async (name: string) => {
    try {
      await removeFromWatchlist(name);
      setEntries((prev) => prev.filter((e) => e.entity_name !== name));
      toast(`Removed "${name}" from watchlist`, "info");
    } catch (err) {
      toast(String(err), "error");
    }
  };

  const staleCount = entries.filter((e) => e.is_stale).length;

  return (
    <section className="watchlist-panel">
      <div className="watchlist-header">
        <div className="watchlist-title">
          <span>📌 Watchlist</span>
          {staleCount > 0 && (
            <span className="stale-badge">{staleCount} stale</span>
          )}
        </div>
        <button
          className="watchlist-add-btn"
          type="button"
          onClick={() => setAdding((v) => !v)}
          title="Add entity to watchlist"
        >
          {adding ? "✕" : "+ Add"}
        </button>
      </div>

      {adding && (
        <form className="watchlist-add-form" onSubmit={handleAdd}>
          <input
            className="watchlist-input"
            type="text"
            placeholder="Company or entity name…"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            autoFocus
          />
          <button className="watchlist-submit-btn" type="submit">Add</button>
        </form>
      )}

      {loading ? (
        <div className="watchlist-empty">Loading…</div>
      ) : entries.length === 0 ? (
        <div className="watchlist-empty">
          No entities pinned. Add entities you want to monitor regularly.
        </div>
      ) : (
        <ul className="watchlist-list">
          {entries.map((e) => (
            <li
              key={e.entity_name}
              className={`watchlist-item ${e.is_stale ? "watchlist-item--stale" : ""}`}
            >
              <button
                className="watchlist-entity-btn"
                type="button"
                onClick={() => onSelectEntity?.(e.entity_name)}
                title={`View scans for ${e.entity_name}`}
              >
                <div className="watchlist-item-top">
                  <span className="watchlist-name">{e.entity_name}</span>
                  {e.last_risk_label && (
                    <span
                      className="watchlist-risk"
                      style={{ color: RISK_COLOR[e.last_risk_label] ?? "#94a3b8" }}
                    >
                      {e.last_risk_score ?? "—"} · {e.last_risk_label}
                    </span>
                  )}
                </div>
                <div className="watchlist-item-meta">
                  <span className={`watchlist-stale-dot ${e.is_stale ? "stale" : "fresh"}`} />
                  <span className="watchlist-age">{timeAgo(e.last_scan_at ?? undefined)}</span>
                  {e.is_stale && <span className="watchlist-stale-label">Re-scan needed</span>}
                </div>
              </button>
              <button
                className="watchlist-remove-btn"
                type="button"
                onClick={() => handleRemove(e.entity_name)}
                title="Remove from watchlist"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
