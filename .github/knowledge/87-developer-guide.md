# AutoDiligence — Developer Guide

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Type hints, `asyncio.to_thread`, tomllib |
| Node.js | 18+ | For the React UI |
| TinyFish API Key | — | Get at https://www.tinyfish.ai |
| Redis | 7+ (optional) | Only needed for distributed TokenVault |

---

## 1. Initial Setup

### Clone & Install

```bash
git clone https://github.com/your-org/auto-diligence-tinyfish.git
cd auto-diligence-tinyfish

# Backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# Frontend
cd ui
npm install
cd ..
```

### Environment

```bash
# Create .env in project root
echo "TINYFISH_API_KEY=sk-tinyfish-your-key-here" > .env
```

---

## 2. Running Locally

### Backend (FastAPI)

```bash
uvicorn src.api.main:app --reload --port 8000
```

API available at: `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs`

### Frontend (Vite)

```bash
cd ui
npm run dev
```

UI available at: `http://localhost:5173`

The Vite dev server proxies `/api/*` to `http://localhost:8000` — no CORS issues.

### Verify TinyFish Connectivity

```bash
python -m src.tinyfish_runner
```

This runs a standalone TinyFish agent and streams all events to stdout. If your API key is valid, you should see `[▶ STARTED]` and `[🔴 LIVE]` events within seconds.

---

## 3. Project Layout

```
auto-diligence-tinyfish/
├── .env                          # API keys (gitignored)
├── requirements.txt
├── config/
│   ├── sources.yaml              # Source registry (URLs, goals, rate limits)
│   └── evasion_profiles.yaml     # Browser anti-detection profiles
├── src/
│   ├── __init__.py               # Exports DiligenceManager, ResearchTask, ResearchResult
│   ├── manager.py                # Central orchestrator
│   ├── agent_factory.py          # Source ID → Agent class + SourceConfig
│   ├── tinyfish_runner.py        # Standalone TinyFish test runner
│   ├── token_vault.py            # Session cookie cache (Redis / in-memory)
│   ├── api/
│   │   ├── main.py               # FastAPI app + CORS + router registration
│   │   ├── store.py              # In-memory ScanStore
│   │   ├── routers/
│   │   │   ├── scans.py          # POST/GET/DELETE /api/scans
│   │   │   ├── findings.py       # GET /api/findings + export + stats + report
│   │   │   ├── agents.py         # SSE /api/agents/stream + events + status
│   │   │   └── personas.py       # GET /api/personas
│   │   └── schemas/
│   │       ├── scan.py           # ScanRequest, ScanResponse, ScanStatus, SourceResult
│   │       ├── finding.py        # Finding, FindingsPage, Severity, FindingStatus
│   │       ├── agent_event.py    # AgentEvent
│   │       └── persona.py        # Persona, DemoTarget, PERSONAS registry
│   ├── sources/
│   │   ├── base.py               # Abstract BaseAgent
│   │   ├── osha_agent.py
│   │   ├── fda_agent.py
│   │   └── sec_agent.py
│   └── utils/
│       ├── validators.py         # validate_request()
│       ├── prompts.py            # Goal template builders
│       └── risk_scorer.py        # ResultAggregator, DiligenceFinding, risk score
└── ui/
    ├── package.json
    ├── vite.config.ts            # /api proxy to :8000
    ├── index.html
    └── src/
        ├── App.tsx               # Router shell
        ├── main.tsx              # Entry point
        ├── api/
        │   ├── client.ts         # Fetch-based API client
        │   └── types.ts          # TypeScript types
        ├── components/           # Reusable UI components
        └── pages/                # Dashboard, NewScan
```

---

## 4. Making a Scan (curl)

```bash
# Start a scan
curl -X POST http://localhost:8000/api/scans \
  -H "Content-Type: application/json" \
  -d '{
    "target": "Tesla Inc",
    "sources": ["us_osha", "us_sec"],
    "persona_id": "compliance_officer"
  }'

# Response → {"scan_id": "3f7a9b2c-...", "status": "pending", ...}
SCAN_ID=3f7a9b2c-...

# Poll for status
curl http://localhost:8000/api/scans/$SCAN_ID

# Watch live events (SSE)
curl -N "http://localhost:8000/api/agents/stream?scan_id=$SCAN_ID"

# Fetch findings once completed
curl "http://localhost:8000/api/findings?scan_id=$SCAN_ID"

# Download CSV
curl -O "http://localhost:8000/api/findings/export/csv?scan_id=$SCAN_ID"

# Executive summary stats
curl "http://localhost:8000/api/findings/stats/summary?scan_id=$SCAN_ID"
```

---

## 5. Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_risk_scorer.py

# Run async tests (pytest-asyncio)
pytest --asyncio-mode=auto
```

### Test Structure (recommended)

```
tests/
├── test_risk_scorer.py       # Unit tests for severity classification + risk scoring
├── test_validators.py        # Unit tests for validate_request()
├── test_agent_factory.py     # Unit tests for AgentFactory config loading
├── test_token_vault.py       # Unit tests for TokenVault save/get/expiry
├── test_api_scans.py         # Integration tests for scan lifecycle
├── test_api_findings.py      # Integration tests for findings + export
└── fixtures/
    └── sample_results.json   # Sample TinyFish result_json for mocking
```

### Mocking TinyFish in Tests

```python
import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_research_completes(mock_tinyfish_result):
    with patch("src.sources.base.TinyFish") as MockTF:
        mock_stream = MagicMock()
        mock_stream.__enter__ = lambda s: iter([
            MagicMock(type=EventType.STARTED, run_id="test-run"),
            MagicMock(type=EventType.COMPLETE, status=RunStatus.COMPLETED,
                      result_json={"cases": [...]})
        ])
        mock_stream.__exit__ = MagicMock(return_value=False)
        MockTF().agent.stream.return_value = mock_stream

        agent = OshaAgent(source=sample_config, token_vault=None)
        results = await agent.research("Tesla Inc", "safety violations")
        assert len(results) > 0
```

---

## 6. Development Workflows

### Adding a new API endpoint

1. Add route to the appropriate router in `src/api/routers/`
2. Add Pydantic schema in `src/api/schemas/` if new request/response shapes are needed
3. Update `__init__.py` exports in `src/api/schemas/`
4. Test with `curl` or the `/docs` Swagger UI

### Modifying the scan flow

The scan lifecycle is entirely in `src/api/routers/scans.py → _run_scan_background()`. Trace the call flow:

```
POST /api/scans
  → create_scan() (sets up store, starts background task)
  → _run_scan_background()
    → DiligenceManager.research()
      → AgentFactory.get_agent() × N
      → asyncio.gather(agent.research() × N)
        → BaseAgent._stream_agent()
          → TinyFish.agent.stream()
    → ResultAggregator.aggregate_all()
    → ResultAggregator.compute_risk_score()
    → scan_store.add_findings()
    → scan_store.update(status=completed)
    → scan_store.close_event_queue() [signals SSE done]
```

### Debugging SSE

If SSE events aren't reaching the UI:

1. Check the queue isn't full (capped at 500 events per scan)
2. Verify `asyncio.run_coroutine_threadsafe` is called with the correct loop
3. Confirm `close_event_queue()` sends the `None` sentinel at the end
4. Browser DevTools → Network → Filter by `EventStream`

### Production Considerations

| Feature | Dev Setup | Production Recommendation |
|---|---|---|
| Scan storage | In-memory `ScanStore` | PostgreSQL with SQLAlchemy |
| Token vault | In-memory dict | Redis |
| API server | `uvicorn --reload` | `gunicorn -w 4 -k uvicorn.workers.UvicornWorker` |
| Frontend | Vite dev server | `npm run build` + serve `ui/dist/` via nginx |
| Auth | None | Add JWT middleware to FastAPI |
| Secrets | `.env` file | AWS Secrets Manager / Azure Key Vault |

---

## 7. Common Issues

### `TINYFISH_API_KEY not found`

`.env` is not in the project root or not loaded. The `dotenv.load_dotenv()` call in `src/api/main.py` handles this at startup — ensure the file exists.

### `ModuleNotFoundError: tinyfish`

TinyFish SDK not installed. Run `pip install tinyfish>=0.1.0`.

### Agents complete immediately with 0 results

TinyFish ran successfully but the target entity had no records at that source. This is a valid result. Check the agent log for `[→ STEP]` lines to confirm navigation happened.

### SSE stream closes immediately

Likely the scan failed before agents had a chance to run. Check `GET /api/scans/{id}` for `status: failed` and `source_results[].error`.

### CORS error from browser

Add your frontend origin to `CORS_ORIGINS` in `.env`:

```bash
CORS_ORIGINS=http://localhost:5173,https://your-production-domain.com
```
