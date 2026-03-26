# AutoDiligence

> **Multi-Agent Regulatory Research Engine powered by [TinyFish Web Agent](https://docs.tinyfish.ai/)**

AutoDiligence automates corporate due-diligence research across US federal enforcement portals. Submit a company name, choose a persona (Compliance Officer, M&A Analyst, ESG Researcher…), and the system fans out AI browser agents to OSHA, FDA, SEC, DOL, and EPA simultaneously. Every step streams live to your UI. Results are normalised, scored 0–100 for risk, and exportable as CSV or an executive report.

```
POST /api/scans  →  5 parallel TinyFish browser agents  →  normalised findings  →  risk score
                          live SSE stream to UI
```

**Stack:** Python 3.11 · FastAPI · TinyFish SDK · asyncio · React 18 · TypeScript · Vite

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Regulatory Sources](#regulatory-sources)
- [Personas](#personas)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Adding a New Source](#adding-a-new-source)
- [Risk Scoring](#risk-scoring)
- [Wiki](#wiki)

---

## Features

| Feature | Details |
|---|---|
| **Multi-source fan-out** | One request hits OSHA, FDA, SEC, DOL, EPA concurrently |
| **Live SSE stream** | Every TinyFish PROGRESS step forwarded to the UI in real time |
| **Live browser view** | TinyFish `STREAMING_URL` events embedded as iframes — watch agents navigate |
| **Persona system** | 6 pre-built role configs: Compliance Officer, M&A Analyst, ESG Researcher, Legal Counsel, Investigative Journalist, Supply Chain Auditor |
| **Risk scoring** | 0–100 score weighted by severity (`critical=30pts`, `high=15pts`, open cases ×1.5) |
| **Evasion profiles** | `standard` / `stealth` / `stealth_proxied` / `high_security` — OSHA uses STEALTH by default |
| **Token Vault** | Shared cookie cache (Redis or in-memory) — agents reuse sessions, no repeated logins |
| **CSV & executive report** | One-click export of all findings |
| **Zero local browser** | All web execution runs on TinyFish cloud infrastructure |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  React UI (Vite :5173)                                           │
│  NewScan   → POST /api/scans                                     │
│  Dashboard → SSE /api/agents/stream → live event log + iframes  │
│            → GET /api/findings → findings table + risk panel     │
└──────────────────────┬───────────────────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼───────────────────────────────────────────┐
│  FastAPI (uvicorn :8000)                                         │
│  /scans  /findings  /agents/stream  /personas                    │
│       │ BackgroundTask                │ asyncio.Queue per scan   │
│  ┌────▼─────────────────────────┐     │                          │
│  │      DiligenceManager        │─────┘ run_coroutine_threadsafe │
│  │  asyncio.gather × N agents   │                                │
│  └────┬──────┬──────┬───────────┘                                │
│  to_thread  to_thread  to_thread  (TinyFish SDK is synchronous)  │
│  ┌────▼──┐ ┌──▼───┐ ┌──▼───┐ ┌──────┐ ┌──────┐                 │
│  │ OSHA  │ │ FDA  │ │ SEC  │ │ DOL  │ │ EPA  │                 │
│  │ Agent │ │Agent │ │Agent │ │Agent │ │Agent │                 │
│  └───┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘                 │
└──────┼────────┼─────────┼────────┼────────┼───────────────────── ┘
       │        │         │                  │  TINYFISH_API_KEY
┌──────▼────────▼─────────▼────────▼─────────▼────────────────────┐
│              TinyFish Cloud Platform                              │
│   Cloud browser runner · STEALTH / LITE profile                  │
│   SSE: STARTED → STREAMING_URL → PROGRESS ×N → COMPLETE          │
└──────┬────────┬─────────┬────────┬───────────────────────────────┘
       ▼        ▼         ▼        ▼
  osha.gov  fda.gov   sec.gov  dol.gov  epa.gov
```

### Concurrency model

TinyFish SDK uses synchronous HTTP streaming. Each agent runs in a thread via `asyncio.to_thread()`. Events bridge back to the asyncio event loop via `run_coroutine_threadsafe()` and are delivered to the UI through a per-scan `asyncio.Queue`.

---

## Regulatory Sources

| ID | Agency | Category | Browser Profile |
|---|---|---|---|
| `us_osha` | US OSHA Enforcement Records | Workplace Safety | STEALTH |
| `us_fda` | FDA Warning Letters & Enforcement | FDA Regulation | LITE |
| `us_sec` | SEC Enforcement Actions | Financial Regulatory | LITE |
| `us_dol` | DOL Wage & Hour Violations | Labor Violations | LITE |
| `us_epa` | EPA Environmental Enforcement | Environmental | LITE |

Sources are configured in [`config/sources.yaml`](config/sources.yaml). Each entry specifies the URL, natural-language goal template, rate limits, retry policy, and browser profile.

---

## Personas

Six pre-built role configurations pre-fill the right sources and query for each use case:

| Persona | Sources | Use Case |
|---|---|---|
| 🛡️ Compliance Officer | All 5 | Board-level risk reports, annual compliance reviews |
| 📊 M&A Analyst | SEC, OSHA, EPA | Pre-acquisition target screening |
| 🌿 ESG Researcher | EPA, OSHA, DOL | ESG scoring, sustainable investment |
| ⚖️ Legal Counsel | SEC, FDA, OSHA | Litigation risk + case status + appeal history |
| 🔍 Investigative Journalist | All 5 | Repeat violations + pattern-of-conduct analysis |
| 🏭 Supply Chain Auditor | OSHA, EPA, DOL | Vendor and supplier risk assessment |

Each persona ships with 3 demo targets (e.g., Tesla Inc, Boeing, ExxonMobil) for instant demonstration.

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- [TinyFish API key](https://www.tinyfish.ai)

### 2. Install

```bash
git clone https://github.com/your-org/auto-diligence-tinyfish.git
cd auto-diligence-tinyfish

# Backend
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS / Linux
pip install -r requirements.txt

# Frontend
cd ui && npm install && cd ..
```

### 3. Configure

```bash
# Project root .env
echo TINYFISH_API_KEY=sk-tinyfish-your-key-here > .env
```

### 4. Run

```bash
# Terminal 1 — API server
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — UI dev server
cd ui && npm run dev
```

Open **http://localhost:5173** → click **New Scan** → pick a persona → enter a company name.

### 5. Verify TinyFish connectivity

```bash
python -m src.tinyfish_runner
```

Streams a live test agent to stdout. Expect `[▶ STARTED]` within a few seconds.

---

## Usage

### UI walkthrough

1. **New Scan** — select a persona (pre-fills sources + query)
2. Enter an entity name, or click a demo target
3. Adjust advanced options: `max_concurrent_agents` (1–20), date range
4. Submit → live **Agent Log** shows each TinyFish step; **Browser Grid** embeds live iframes
5. Once complete: **Findings** table (filter by severity / status / source), **Risk Panel**, **Timeline**
6. **CSV export** or **Executive Report** from the findings toolbar

### curl

```bash
# Start a scan
curl -X POST http://localhost:8000/api/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "Tesla Inc", "persona_id": "compliance_officer"}'

SCAN_ID=<scan_id from response>

# Watch live events
curl -N "http://localhost:8000/api/agents/stream?scan_id=$SCAN_ID"

# Fetch findings (filter to critical)
curl "http://localhost:8000/api/findings?scan_id=$SCAN_ID&severity=critical"

# Download CSV
curl -O "http://localhost:8000/api/findings/export/csv?scan_id=$SCAN_ID"
```

### Python

```python
import asyncio
from src.manager import DiligenceManager

async def main():
    manager = DiligenceManager(
        sources=["us_osha", "us_sec"],
        max_concurrent_agents=5,
    )
    results = await manager.research(
        target="Tesla Inc",
        query="workplace safety violations and enforcement actions",
    )
    for source_id, result in results.items():
        print(f"{source_id}: {result.status} — {len(result.data)} records")
    await manager.close()

asyncio.run(main())
```

---

## API Reference

Full reference: [`.github/knowledge/82-api-reference.md`](.github/knowledge/82-api-reference.md)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Service health check |
| `POST` | `/api/scans` | Start scan (202 Accepted, async) |
| `GET` | `/api/scans` | List all scans |
| `GET` | `/api/scans/{id}` | Scan status + source results |
| `DELETE` | `/api/scans/{id}` | Cancel / delete scan |
| `GET` | `/api/findings` | Paginated findings (filterable) |
| `GET` | `/api/findings/{id}` | Single finding |
| `GET` | `/api/findings/export/csv` | CSV download |
| `GET` | `/api/findings/stats/summary` | Aggregate stats + exposure |
| `GET` | `/api/findings/report/executive` | Structured executive report |
| `GET` | `/api/agents/stream` | **SSE** live agent event stream |
| `GET` | `/api/agents/events` | Full event history |
| `GET` | `/api/agents/status` | Source completion snapshot |
| `GET` | `/api/personas` | List personas |
| `GET` | `/api/personas/{id}` | Single persona |

Interactive docs: **http://localhost:8000/docs**

---

## Configuration

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `TINYFISH_API_KEY` | ✅ | TinyFish API key from tinyfish.ai |
| `CORS_ORIGINS` | ❌ | Comma-separated allowed origins. Default: `http://localhost:5173,...` |
| `REDIS_URL` | ❌ | Redis connection string for distributed TokenVault |

### `config/sources.yaml`

Defines each regulatory source: URL, goal template (`{{company_name}}`, `{{date_from}}`, `{{date_to}}`), browser profile, rate limits, retry policy.

### `config/evasion_profiles.yaml`

Four named profiles — `standard`, `stealth`, `stealth_proxied`, `high_security`. The `source_profile_mapping` section assigns a profile to each source ID.

---

## Project Structure

```
auto-diligence-tinyfish/
├── .env                          # TINYFISH_API_KEY (not committed)
├── requirements.txt
├── config/
│   ├── sources.yaml              # Source registry + goal templates
│   └── evasion_profiles.yaml    # Browser anti-detection profiles
├── src/
│   ├── manager.py                # DiligenceManager — orchestrator
│   ├── agent_factory.py          # source ID → agent class + SourceConfig
│   ├── tinyfish_runner.py        # Standalone TinyFish test runner
│   ├── token_vault.py            # SessionToken cache (Redis / in-memory)
│   ├── api/
│   │   ├── main.py               # FastAPI app + CORS + routers
│   │   ├── store.py              # In-memory ScanStore
│   │   ├── routers/
│   │   │   ├── scans.py          # Scan lifecycle endpoints
│   │   │   ├── findings.py       # Findings + CSV + stats + executive report
│   │   │   ├── agents.py         # SSE stream + event history + status
│   │   │   └── personas.py      # Persona list / detail
│   │   └── schemas/
│   │       ├── scan.py           # ScanRequest, ScanResponse, ScanStatus
│   │       ├── finding.py        # Finding, FindingsPage, Severity
│   │       ├── agent_event.py    # AgentEvent
│   │       └── persona.py        # Persona, DemoTarget, registry
│   ├── sources/
│   │   ├── base.py               # Abstract BaseAgent (stream, retry, emit)
│   │   ├── osha_agent.py
│   │   ├── fda_agent.py
│   │   └── sec_agent.py
│   └── utils/
│       ├── validators.py         # validate_request()
│       ├── prompts.py            # Goal template builders
│       └── risk_scorer.py        # ResultAggregator + 0–100 risk score
└── ui/
    ├── src/
    │   ├── App.tsx               # Router shell
    │   ├── api/
    │   │   ├── client.ts         # Fetch + SSE API client
    │   │   └── types.ts          # TypeScript types
    │   ├── components/
    │   │   ├── AgentLog.tsx      # Live event log
    │   │   ├── BrowserGrid.tsx   # Live TinyFish browser iframes
    │   │   ├── FindingsTable.tsx # Paginated findings table
    │   │   ├── ScorePanel.tsx    # Risk gauge + breakdown
    │   │   └── ...
    │   └── pages/
    │       ├── Dashboard.tsx
    │       └── NewScan.tsx
    └── vite.config.ts            # /api proxy → :8000
```

---

## Adding a New Source

1. Add source config to [`config/sources.yaml`](config/sources.yaml)
2. Create `src/sources/ftc_agent.py` extending `BaseAgent` — implement `_build_goal()` and `_normalize_result()`
3. Register in `src/agent_factory.py`: `_AGENT_REGISTRY["us_ftc"] = FtcAgent`
4. *(Optional)* add to `ALL_SOURCES` in `ui/src/pages/NewScan.tsx`

Full walkthrough: [`.github/knowledge/86-configuration-guide.md`](.github/knowledge/86-configuration-guide.md)

---

## Risk Scoring

Findings are scored 0–100:

```
weights = { critical: 30, high: 15, medium: 5, low: 1 }
open cases × 1.5 multiplier
score = min(100, Σ weight × multiplier)
```

Severity is derived from keyword matching on `violation_type` (`"willful"` / `"fraud"` → critical) and penalty thresholds ($500k+ → critical, $100k+ → high, $10k+ → medium).

| Score | Label |
|---|---|
| 70–100 | Critical Risk |
| 40–69 | High Risk |
| 15–39 | Medium Risk |
| 1–14 | Low Risk |
| 0 | Clean |

Full algorithm: [`.github/knowledge/85-risk-scoring.md`](.github/knowledge/85-risk-scoring.md)

---

## Wiki

Detailed documentation in [`.github/knowledge/`](.github/knowledge/):

| File | Contents |
|---|---|
| [`80-project-architecture.md`](.github/knowledge/80-project-architecture.md) | System diagram, request lifecycle, concurrency model, design decisions |
| [`81-backend-components.md`](.github/knowledge/81-backend-components.md) | All Python classes, methods, data models |
| [`82-api-reference.md`](.github/knowledge/82-api-reference.md) | Full REST API with example payloads |
| [`83-frontend-components.md`](.github/knowledge/83-frontend-components.md) | Every React component + API client |
| [`84-personas-system.md`](.github/knowledge/84-personas-system.md) | All 6 personas + data model + extension guide |
| [`85-risk-scoring.md`](.github/knowledge/85-risk-scoring.md) | Severity classification + scoring algorithm |
| [`86-configuration-guide.md`](.github/knowledge/86-configuration-guide.md) | Env vars, YAML config, adding new sources |
| [`87-developer-guide.md`](.github/knowledge/87-developer-guide.md) | Local setup, testing, debugging, production notes |

---

## License

[MIT](LICENSE)
