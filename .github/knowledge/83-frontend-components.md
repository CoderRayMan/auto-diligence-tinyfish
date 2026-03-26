# AutoDiligence — Frontend Components Reference

The UI is a React SPA built with **Vite + TypeScript**. It communicates with the FastAPI backend over HTTP and SSE.

---

## Technology Stack

| Tool | Version | Role |
|---|---|---|
| React | 18 | Component framework |
| TypeScript | 5 | Type safety |
| React Router DOM | 6 | Client-side routing |
| Vite | 5 | Dev server + bundler |
| CSS Modules (plain) | — | Per-component styles |

No UI framework (no MUI, no Tailwind) — all styles are hand-written CSS.

---

## App Shell

### `ui/src/main.tsx`
Entry point. Mounts `<App>` into `#root` with `StrictMode`.

### `ui/src/App.tsx`
Top-level router:

```tsx
<BrowserRouter>
  <AppBar />       {/* fixed header */}
  <Routes>
    <Route path="/"          element={<Dashboard />} />
    <Route path="/new-scan"  element={<NewScan />} />
    <Route path="*"          element={<Navigate to="/" />} />
  </Routes>
</BrowserRouter>
```

---

## Pages

### `ui/src/pages/Dashboard.tsx`

Main landing page. Shows all scans and live run state.

**State managed:**

| State | Type | Description |
|---|---|---|
| `scans` | `Scan[]` | All scans (polled every 3s while any are running) |
| `selectedScan` | `Scan \| null` | Currently viewed scan |
| `agentEvents` | `AgentEvent[]` | Live events from SSE |
| `findings` | `FindingsPage \| null` | Findings for selected scan |
| `stats` | `Record<string,unknown> \| null` | Summary stats |

**Behaviour:**
- Polls `GET /api/scans` every 3s while any scan is `running`
- On scan selection: fetches missed events via `getAgentEventHistory()`, then subscribes to live SSE
- Passes `agentEvents` to `<AgentLog>` and `<BrowserGrid>` simultaneously
- Cleans up SSE subscription on scan deselection or unmount

---

### `ui/src/pages/NewScan.tsx`

Scan creation form.

**State managed:**

| State | Type | Description |
|---|---|---|
| `personas` | `Persona[]` | Loaded from `/api/personas` on mount |
| `selectedPersona` | `Persona \| null` | Currently applied persona |
| `form` | `FormState` | `{target, query, sources, maxAgents, personaId}` |
| `submitting` | `boolean` | Disables submit button during API call |
| `showAdvanced` | `boolean` | Toggle advanced options section |

**Behaviour:**
1. Loads personas from API on mount
2. Selecting a persona pre-fills `sources` + `query` from persona config
3. Clicking a `DemoTarget` sets `form.target`
4. Submit → `POST /api/scans` → navigate to `/?scan_id={id}`
5. Client-side validation: target ≥ 2 chars, at least 1 source selected

---

## Components

### `AppBar.tsx`

Fixed top navigation bar.

- App name + logo
- Navigation links (Dashboard, New Scan)
- Health check indicator (polls `GET /api/health` every 30s; shows green/red dot)
- Keyboard shortcut hints

---

### `ContextStrip.tsx`

Horizontal scan metadata strip shown above live results.

**Props:** `scan: Scan`

Displays:
- Target entity name
- Persona label (if set)
- Scan status badge (`pending` / `running` / `completed` / `failed`)
- Sources progress bar (completed / total)
- Risk score + label badge (coloured by risk level)
- Elapsed / total time

---

### `BrowserGrid.tsx`

Live browser stream viewer. Shows embedded iframes for each active TinyFish browser session.

**Props:** `events: AgentEvent[]`

**Behaviour:**
- Watches `AgentEvent[]` for events with `agent_tag === "STREAMING_URL"`
- For each new `streaming_url`, creates a card with `<iframe src={streaming_url}>`
- Cards are labeled by `source_id`
- When an agent completes or fails, its card greys out
- Grid is responsive: 1–3 columns depending on active agent count

**This is the "live view" feature** — users can watch TinyFish browsers navigate government sites in real time.

---

### `AgentLog.tsx`

Scrolling activity log of agent events.

**Props:** `events: AgentEvent[], scan: Scan`

Renders each `AgentEvent` as a log line:

```
10:01:15  us_osha  [RUNNING]       Starting TinyFish agent (attempt 1)
10:01:17  us_osha  [STREAMING_URL] Browser live: https://stream.tinyfish.ai/...
10:01:18  us_osha  [RUNNING]       Navigating to OSHA enforcement search
10:01:35  us_osha  [RUNNING]       Entering search term: Tesla Inc
10:02:10  us_osha  [COMPLETED]     Found 12 records
```

- Auto-scrolls to bottom as new events arrive
- `FAILED` lines are styled in red; `COMPLETED` in green; `STREAMING_URL` in blue
- Grouped by `source_id` with colour coding per source

---

### `FindingsTable.tsx`

Paginated, sortable table of regulatory findings.

**Props:** `scanId: string`

**Features:**
- Loads findings via `GET /api/findings?scan_id=...`
- Filter controls: severity dropdown, status dropdown, source dropdown
- Sortable columns: severity, penalty amount, date
- Severity badges: colour-coded (`critical` = red, `high` = orange, `medium` = yellow, `low` = blue)
- Status badges: `open` (red), `settled` (green), `closed` (grey), `appealed` (orange)
- Click a row → opens `<DetailsDrawer>`
- Pagination: prev/next, page size selector
- CSV export button → calls `downloadFindingsCSV(scanId)`

---

### `ScorePanel.tsx`

Risk score summary panel.

**Props:** `scan: Scan, stats: Record<string,unknown>`

Displays:
- Large numeric risk score (0–100) with animated fill gauge
- Risk label (`Clean` / `Low Risk` / `Medium Risk` / `High Risk` / `Critical Risk`)
- Donut chart breakdown by severity
- Total financial exposure formatted (`$2.5M`, `$450k`)
- Top 5 violations by frequency
- Source coverage breakdown

---

### `DetailsDrawer.tsx`

Slide-in side panel for a single finding.

**Props:** `finding: Finding | null, onClose: () => void`

Shows all finding fields in a structured layout:
- Case ID + source badge
- Severity + status chips
- Entity name + jurisdiction
- Violation type
- Penalty amount (formatted)
- Decision date
- Full description
- Source URL (external link)

---

### `Timeline.tsx`

Chronological timeline of findings plotted by decision date.

**Props:** `findings: Finding[]`

- SVG-based or CSS-based horizontal/vertical timeline
- Colour-coded dots by severity
- Hovering a dot shows a tooltip with case summary
- Useful for visualising patterns of repeat violations over time

---

## API Client (`ui/src/api/client.ts`)

Thin fetch-based client. No Axios or SWR. All functions are async and typed.

| Function | Method | Endpoint |
|---|---|---|
| `createScan(req)` | POST | `/api/scans` |
| `getScan(id)` | GET | `/api/scans/{id}` |
| `listScans()` | GET | `/api/scans` |
| `cancelScan(id)` | DELETE | `/api/scans/{id}` |
| `getFindings(id, opts)` | GET | `/api/findings` |
| `getAgentEventHistory(id)` | GET | `/api/agents/events` |
| `subscribeAgentEvents(id, onEvent, onDone)` | SSE | `/api/agents/stream` |
| `getAgentStatus(id)` | GET | `/api/agents/status` |
| `listPersonas()` | GET | `/api/personas` |
| `downloadFindingsCSV(id)` | — | Triggers browser download |
| `getFindingsStats(id)` | GET | `/api/findings/stats/summary` |
| `rerunScan(id)` | POST | Re-submits same scan parameters |

### SSE Subscription Pattern

```typescript
// Open SSE before scan is done (catch all events from the start)
const unsub = subscribeAgentEvents(
  scanId,
  (event) => setAgentEvents(prev => [...prev, event]),
  () => setStreaming(false),
);

// Cleanup on unmount
return () => unsub();
```

---

## TypeScript Types (`ui/src/api/types.ts`)

Mirror of backend Pydantic schemas:

```typescript
type ScanStatus   = "pending" | "running" | "completed" | "failed" | "cancelled";
type Severity     = "critical" | "high" | "medium" | "low";
type FindingStatus = "open" | "settled" | "closed" | "appealed" | "unknown";

interface Scan { scan_id, status, target, query, persona_id, created_at, 
                 completed_at, sources_total, sources_completed, sources_failed,
                 risk_score, risk_label, findings_count, source_results }

interface Finding { finding_id, scan_id, source_id, case_id, case_type,
                    entity_name, violation_type, decision_date, penalty_amount,
                    severity, status, description, source_url, jurisdiction }

interface AgentEvent { scan_id, source_id, agent_tag, message, timestamp, streaming_url? }

interface Persona { id, label, icon, description, color, default_sources,
                    default_query, focus_areas, demo_targets }
```

---

## Running the UI

```bash
cd ui
npm install
npm run dev      # Vite dev server on :5173 (proxies /api to :8000)
npm run build    # Production build → ui/dist/
npm run preview  # Preview production build
```

The Vite dev server is pre-configured to proxy `/api/*` to `http://localhost:8000`, so CORS is avoided in development.
