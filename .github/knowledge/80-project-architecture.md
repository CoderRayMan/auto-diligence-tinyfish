# AutoDiligence — Project Architecture

> **AutoDiligence** is a multi-agent regulatory research engine that wraps [TinyFish Web Agent](https://docs.tinyfish.ai/) capabilities to automate due-diligence scraping across US federal enforcement portals (OSHA, FDA, SEC, DOL, EPA). A single API call fans out to N concurrent browser agents, streams live events over SSE, normalises results, and scores overall entity risk.

---

## 1. High-Level System Diagram

```mermaid
graph TD
    UI["React UI\n(Vite + TypeScript)"]
    API["FastAPI Backend\n(uvicorn :8000)"]
    MGR["DiligenceManager\n(Orchestrator)"]
    FAC["AgentFactory\n(Source → Agent class)"]
    TVT["TokenVault\n(Session cache)"]
    AGT1["OshaAgent"]
    AGT2["FdaAgent"]
    AGT3["SecAgent"]
    AGTN["...GenericAgent"]
    TF["TinyFish Platform\n(Cloud browser runners)"]
    OSHA["osha.gov"]
    FDA["fda.gov"]
    SEC["sec.gov"]
    DOL["dol.gov"]
    EPA["epa.gov"]
    STORE["ScanStore\n(In-memory)"]
    SSE["SSE Queue\n(asyncio.Queue)"]

    UI -- "POST /api/scans" --> API
    UI -- "GET /api/agents/stream (SSE)" --> SSE
    UI -- "GET /api/findings" --> API
    API --> STORE
    API -- "BackgroundTask" --> MGR
    MGR --> FAC
    FAC --> AGT1
    FAC --> AGT2
    FAC --> AGT3
    FAC --> AGTN
    AGT1 -- "TINYFISH_API_KEY" --> TF
    AGT2 --> TF
    AGT3 --> TF
    AGTN --> TF
    TF --> OSHA
    TF --> FDA
    TF --> SEC
    TF --> DOL
    TF --> EPA
    AGT1 -- "SSE events" --> SSE
    AGT2 --> SSE
    AGT3 --> SSE
    MGR --> TVT
    SSE --> UI
    STORE --> UI
```

---

## 2. Layered Architecture

The system is divided into five clean layers:

| Layer | Location | Responsibility |
|---|---|---|
| **Presentation** | `ui/` | React SPA — scan creation, live agent log, findings table, risk score |
| **API** | `src/api/` | FastAPI routers, Pydantic schemas, CORS, SSE endpoint |
| **Orchestration** | `src/manager.py`, `src/agent_factory.py` | Task decomposition, concurrency, result aggregation |
| **Agent** | `src/sources/` | TinyFish API calls, goal rendering, result normalisation |
| **Infrastructure** | `src/token_vault.py`, `config/` | Session state, evasion profiles, source registry |

---

## 3. Request Lifecycle

```mermaid
sequenceDiagram
    participant Browser
    participant FastAPI
    participant Manager
    participant AgentFactory
    participant BaseAgent
    participant TinyFish
    participant GovSite

    Browser->>FastAPI: POST /api/scans {target, query, sources, persona_id}
    FastAPI-->>Browser: 202 Accepted {scan_id, status: "pending"}
    FastAPI->>Manager: BackgroundTask(_run_scan_background)

    Browser->>FastAPI: GET /api/agents/stream?scan_id=X (SSE)
    FastAPI-->>Browser: SSE stream opened

    Manager->>AgentFactory: get_agent(source_id) × N
    AgentFactory-->Manager: [OshaAgent, FdaAgent, SecAgent, ...]
    Manager->>BaseAgent: research(target, query, event_callback) [concurrent]

    BaseAgent->>TinyFish: agent.stream(url, goal, browser_profile)
    TinyFish-->>BaseAgent: SSE: STARTED
    TinyFish-->>BaseAgent: SSE: STREAMING_URL
    FastAPI-->>Browser: SSE: agent_event {STREAMING_URL}
    TinyFish->>GovSite: Browser navigates, searches, extracts
    TinyFish-->>BaseAgent: SSE: PROGRESS × N
    FastAPI-->>Browser: SSE: agent_event {RUNNING, step description}
    TinyFish-->>BaseAgent: SSE: COMPLETE {result_json}
    BaseAgent-->>Manager: normalised cases[]

    Manager->>Manager: ResultAggregator.aggregate_all()
    Manager->>Manager: ResultAggregator.compute_risk_score()
    Manager->>FastAPI: update ScanStore (findings, risk_score)
    FastAPI-->>Browser: SSE: done
    Browser->>FastAPI: GET /api/findings?scan_id=X
    FastAPI-->>Browser: FindingsPage {findings[]}
```

---

## 4. Concurrency Model

```
asyncio event loop (FastAPI / uvicorn)
│
├── Route handler: POST /api/scans  ─────────── returns immediately (202)
│   └── BackgroundTask: _run_scan_background()
│       └── await manager.research()
│           └── asyncio.gather(*[
│                   asyncio.to_thread(agent.research, ...)   ← thread per source
│                   asyncio.to_thread(agent.research, ...)   ← thread per source
│                   ...up to max_concurrent_agents (default 5)
│               ])
│
└── Route handler: GET /api/agents/stream  ──── held open for SSE
    └── AsyncGenerator: reads asyncio.Queue per scan_id
        ← events pushed thread-safely via asyncio.run_coroutine_threadsafe()
```

**Key design decision:** TinyFish SDK uses synchronous HTTP streaming (blocking `for event in stream`). Each agent runs in a thread via `asyncio.to_thread()`, then bridges back to the event loop via `run_coroutine_threadsafe()` for SSE delivery.

---

## 5. Component Dependency Graph

```mermaid
graph LR
    main["api/main.py"] --> scans["routers/scans.py"]
    main --> findings["routers/findings.py"]
    main --> agents_r["routers/agents.py"]
    main --> personas_r["routers/personas.py"]

    scans --> store["api/store.py"]
    scans --> manager["manager.py"]
    scans --> risk["utils/risk_scorer.py"]
    scans --> schemas_s["schemas/scan.py"]
    scans --> schemas_f["schemas/finding.py"]
    scans --> schemas_e["schemas/agent_event.py"]
    scans --> schemas_p["schemas/persona.py"]

    manager --> factory["agent_factory.py"]
    manager --> vault["token_vault.py"]
    manager --> validators["utils/validators.py"]

    factory --> base["sources/base.py"]
    factory --> osha["sources/osha_agent.py"]
    factory --> fda["sources/fda_agent.py"]
    factory --> sec["sources/sec_agent.py"]
    factory --> yaml_cfg["config/sources.yaml"]

    base --> tinyfish_sdk["tinyfish SDK"]
    osha --> base
    fda --> base
    sec --> base
```

---

## 6. Key Design Principles

### A. TinyFish as the Browser Runtime
AutoDiligence **never runs a local browser**. All web navigation, authentication, and data extraction runs on the TinyFish cloud platform. The system's job is to compose smart natural-language goals and process what comes back.

### B. Goal-First Programming
Each agent expresses its intent as a human-readable paragraph (a "goal"). TinyFish figures out how to click, search, and extract. This makes adding new regulatory sources as simple as writing a new `_build_goal()` method.

### C. Event-Driven Observability
Every TinyFish SDK event (STARTED, STREAMING_URL, PROGRESS, COMPLETE) is forwarded in real-time to the UI via SSE. Users watch agents work live—they can even embed the live browser stream in the UI via an `<iframe>` from the STREAMING_URL.

### D. Source-Agnostic Orchestration
The `DiligenceManager` knows nothing about individual sites. It hands source IDs to `AgentFactory`, which maps them to the right agent class and YAML config. Adding a new source (e.g., FTC) requires:
1. A new entry in `config/sources.yaml`
2. A new `FtcAgent` class in `src/sources/`
3. Registration in `AgentFactory._AGENT_REGISTRY`

### E. Stateful Session Reuse (TokenVault)
When multiple agents log into the same site, the second agent reuses the first's cookies via `TokenVault`, avoiding redundant login flows. Supports both in-memory (dev) and Redis (production) backends.
