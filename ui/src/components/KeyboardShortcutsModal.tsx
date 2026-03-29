import React from "react";
import { X } from "lucide-react";
import "./KeyboardShortcutsModal.css";

interface Props {
  onClose: () => void;
}

const SHORTCUTS = [
  { key: "N", description: "New scan" },
  { key: "D", description: "Dashboard" },
  { key: "W", description: "Toggle watchlist" },
  { key: "C", description: "Compare scans" },
  { key: "R", description: "Re-run active scan" },
  { key: "E", description: "Export findings as CSV" },
  { key: "P", description: "Open executive report" },
  { key: "T", description: "Toggle timeline / table view" },
  { key: "?", description: "Show this help" },
  { key: "Esc", description: "Close modals / drawers" },
];

export default function KeyboardShortcutsModal({ onClose }: Props) {
  return (
    <>
      <div className="kbd-modal-overlay" onClick={onClose} />
      <div className="kbd-modal" role="dialog" aria-label="Keyboard shortcuts">
        <div className="kbd-modal-header">
          <h3>Keyboard Shortcuts</h3>
          <button className="kbd-modal-close" onClick={onClose} type="button" aria-label="Close keyboard shortcuts">
            <X size={14} />
          </button>
        </div>
        <ul className="kbd-list">
          {SHORTCUTS.map(({ key, description }) => (
            <li key={key} className="kbd-item">
              <kbd className="kbd-key">{key}</kbd>
              <span className="kbd-desc">{description}</span>
            </li>
          ))}
        </ul>
        <p className="kbd-footer">Press <kbd className="kbd-key-inline">Esc</kbd> or click outside to close</p>
      </div>
    </>
  );
}
