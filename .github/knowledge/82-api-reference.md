# AutoDiligence — REST API Reference

Base URL: `http://localhost:8000/api`

All request/response bodies use JSON. All timestamps are ISO 8601 UTC.

---

## Health Check

### `GET /api/health`

```json
{ "status": "ok", "service": "autodiligence" }
```

---

## Scans

### `POST /api/scans` — Start a Scan

Initiates a new diligence scan. Returns immediately (HTTP 202); the scan runs in the background.

**Request body:**

```json
{
  "target": "Tesla Inc",
  "query": "workplace safety and environmental violations",
  "sources": ["us_osha", "us_fda", "us_sec"],
  "persona_id": "compliance_officer",
  "date_from": "2020-01-01",
  "date_to": "2024-12-31",
  "max_concurrent_agents": 5
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `target` | string | ✅ | Entity to research (2–500 chars) |
| `query` | string | ❌ | Research focus. Default: `"regulatory violations and enforcement actions"` |
| `sources` | string[] | ❌ | Source IDs. Default: all 5 configured sources |
| `persona_id` | string | ❌ | Persona ID; pre-fills sources + query from persona config |
| `date_from` | string | ❌ | ISO date filter start (passed into goal template) |
| `date_to` | string | ❌ | ISO date filter end |
| `max_concurrent_agents` | int | ❌ | 1–20. Default: 5 |

**Response: `202 Accepted`**

```json
{
  "scan_id": "3f7a9b2c-...",
  "status": "pending",
  "target": "Tesla Inc",
  "query": "workplace safety and environmental violations",
  "persona_id": "compliance_officer",
  "created_at": "2026-03-26T10:00:00Z",
  "completed_at": null,
  "sources_total": 3,
  "sources_completed": 0,
  "sources_failed": 0,
  "risk_score": null,
  "risk_label": null,
  "findings_count": 0,
  "source_results": []
}
```

**Scan status lifecycle:**

```
pending → running → completed
                 ↘ failed
```

---

### `GET /api/scans` — List All Scans

Returns all scans in reverse-chronological order.

**Response: `200 OK`** — array of `ScanResponse` objects.

---

### `GET /api/scans/{scan_id}` — Get Scan

**Response: `200 OK`** — single `ScanResponse`.

Populated fields once completed:

```json
{
  "status": "completed",
  "completed_at": "2026-03-26T10:04:30Z",
  "sources_total": 3,
  "sources_completed": 2,
  "sources_failed": 1,
  "risk_score": 42,
  "risk_label": "High Risk",
  "findings_count": 17,
  "source_results": [
    {
      "source_id": "us_osha",
      "status": "completed",
      "records_found": 12,
      "execution_time_s": 45.3,
      "error": null
    },
    {
      "source_id": "us_fda",
      "status": "failed",
      "records_found": 0,
      "execution_time_s": 30.1,
      "error": "TinyFish run failed: AGENT_FAILURE"
    }
  ]
}
```

---

### `DELETE /api/scans/{scan_id}` — Cancel / Delete a Scan

Marks scan as `cancelled` and removes it from the store.

**Response: `204 No Content`**

---

## Findings

### `GET /api/findings` — List Findings (paginated + filtered)

**Query parameters:**

| Param | Type | Description |
|---|---|---|
| `scan_id` | string | ✅ Required |
| `severity` | string | Filter: `critical` \| `high` \| `medium` \| `low` |
| `status` | string | Filter: `open` \| `settled` \| `closed` \| `appealed` |
| `source_id` | string | Filter by source, e.g. `us_osha` |
| `page` | int | Default: 1 |
| `page_size` | int | Default: 50, max: 200 |

**Response: `200 OK`**

```json
{
  "scan_id": "3f7a9b2c-...",
  "total": 17,
  "page": 1,
  "page_size": 50,
  "findings": [
    {
      "finding_id": "us_osha_2023-OSHA-0042",
      "scan_id": "3f7a9b2c-...",
      "source_id": "us_osha",
      "case_id": "2023-OSHA-0042",
      "case_type": "us_osha",
      "entity_name": "Tesla Inc",
      "violation_type": "serious",
      "decision_date": "2023-07-15",
      "penalty_amount": 145000,
      "severity": "high",
      "status": "settled",
      "description": "Failure to provide adequate machine guarding on stamping press.",
      "source_url": "https://www.osha.gov/...",
      "jurisdiction": "California DOSH"
    }
  ]
}
```

---

### `GET /api/findings/{finding_id}` — Single Finding

**Query params:** `scan_id` (required)

**Response: `200 OK`** — single `Finding` object.

---

### `GET /api/findings/export/csv` — Download CSV

**Query params:** `scan_id` (required)

Downloads all findings as a CSV file. Filename: `autodiligence_{target}_{scan_id[:8]}.csv`

**Columns:** `finding_id`, `source_id`, `case_id`, `entity_name`, `violation_type`, `severity`, `status`, `penalty_amount`, `decision_date`, `jurisdiction`, `description`, `source_url`

---

### `GET /api/findings/stats/summary` — Aggregate Statistics

**Query params:** `scan_id` (required)

**Response:**

```json
{
  "scan_id": "...",
  "target": "Tesla Inc",
  "persona_id": "compliance_officer",
  "total_findings": 17,
  "by_severity": { "critical": 1, "high": 8, "medium": 5, "low": 3 },
  "by_source": { "us_osha": 12, "us_sec": 5 },
  "by_status": { "open": 4, "settled": 10, "closed": 3 },
  "total_exposure": 2450000.00,
  "top_violations": [
    { "type": "serious", "count": 7 },
    { "type": "willful", "count": 3 }
  ],
  "top_penalties": [
    {
      "case_id": "...",
      "source_id": "us_sec",
      "penalty_amount": 1500000,
      "violation_type": "fraud",
      "severity": "critical"
    }
  ],
  "risk_score": 42,
  "risk_label": "High Risk"
}
```

---

### `GET /api/findings/report/executive` — Executive Report

**Query params:** `scan_id` (required)

Generates a structured, narrative-ready executive diligence report.

**Response:**

```json
{
  "scan_id": "...",
  "target": "Tesla Inc",
  "generated_at": "2026-03-26T10:05:00Z",
  "overall_risk": { "score": 42, "label": "High Risk" },
  "executive_summary": "Tesla Inc has 17 enforcement findings across 2 federal agencies...",
  "total_financial_exposure": "$2.5M",
  "sections": [
    {
      "title": "Critical & High Severity Findings",
      "findings": [...]
    },
    {
      "title": "Open Matters Requiring Attention",
      "findings": [...]
    }
  ],
  "recommendations": [...]
}
```

---

## Agents (SSE + Status)

### `GET /api/agents/stream` — Live SSE Stream

**Query params:** `scan_id` (required)

Opens a persistent SSE connection. Events are delivered as they happen.

**Event types:**

| Event name | Payload | Description |
|---|---|---|
| `agent_event` | `AgentEvent` JSON | Agent activity (RUNNING, COMPLETED, FAILED, STREAMING_URL) |
| `ping` | `""` | Keep-alive every 30s of inactivity |
| `done` | `{"scan_id": "..."}` | Scan finished; close the connection |

**`AgentEvent` schema:**

```json
{
  "scan_id": "3f7a9b2c-...",
  "source_id": "us_osha",
  "agent_tag": "STREAMING_URL",
  "message": "Browser live: https://stream.tinyfish.ai/...",
  "timestamp": "2026-03-26T10:01:15Z",
  "streaming_url": "https://stream.tinyfish.ai/..."
}
```

**`agent_tag` values:**

| Tag | Meaning |
|---|---|
| `RUNNING` | Agent is executing a step |
| `STREAMING_URL` | Live browser iframe URL is available |
| `COMPLETED` | Agent finished successfully |
| `FAILED` | Agent failed (see `message` for reason) |
| `WAITING` | Agent is paused (rate limiting / jitter) |

---

### `GET /api/agents/events` — Full Event History

**Query params:** `scan_id` (required)

Returns all events ever emitted for the scan. Use before opening the SSE stream to catch missed events.

```json
{
  "scan_id": "...",
  "events": [ ...AgentEvent[] ]
}
```

---

### `GET /api/agents/status` — Agent Completion Snapshot

**Query params:** `scan_id` (required)

```json
{
  "scan_id": "...",
  "status": "running",
  "sources_total": 5,
  "sources_completed": 3,
  "sources_failed": 1,
  "source_results": [...]
}
```

---

## Personas

### `GET /api/personas` — List Personas

Returns all 6 pre-built persona configurations.

```json
[
  {
    "id": "compliance_officer",
    "label": "Compliance Officer",
    "icon": "🛡️",
    "description": "Full regulatory sweep across all federal agencies...",
    "color": "#3b82f6",
    "default_sources": ["us_osha", "us_fda", "us_sec", "us_dol", "us_epa"],
    "default_query": "Find all enforcement actions, violations, penalties...",
    "focus_areas": ["Enforcement Actions", "Consent Orders", "Penalty History"],
    "demo_targets": [
      {
        "name": "Tesla Inc",
        "description": "Electric vehicle manufacturer — OSHA, SEC, and EPA exposure",
        "query_override": null
      }
    ]
  }
]
```

### `GET /api/personas/{persona_id}` — Single Persona

Returns one persona by ID.

---

## Error Responses

All errors follow FastAPI's default format:

```json
{
  "detail": "Scan not found"
}
```

| HTTP Status | Condition |
|---|---|
| `400` | Invalid request body (Pydantic validation failure) |
| `404` | Scan or finding not found |
| `422` | Unprocessable entity (field constraint violation) |
| `500` | Unexpected server error |
