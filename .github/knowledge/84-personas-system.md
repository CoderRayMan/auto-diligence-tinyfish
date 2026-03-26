# AutoDiligence — Personas System

Personas are pre-built scan configurations that model specific real-world user roles. Selecting a persona pre-fills the scan form with purpose-tuned regulatory sources, query language, and demo targets.

---

## Purpose

Without personas, every user must know:
- Which of the 5 sources is relevant to their use case
- How to phrase the query for maximum recall
- What example entities best demonstrate the system

Personas eliminate that friction. A compliance officer and an ESG researcher need completely different data — personas encode that domain knowledge.

---

## Available Personas

### 🛡️ Compliance Officer (`compliance_officer`)

- **Color:** Blue (`#3b82f6`)
- **Sources:** All 5 (OSHA, FDA, SEC, DOL, EPA)
- **Focus:** Full regulatory sweep — enforcement actions, consent orders, penalty history
- **Query:** `Find all enforcement actions, violations, penalties, consent orders, and regulatory warnings`
- **For:** Board-level risk reports, annual compliance reviews

**Demo targets:** Tesla Inc, Johnson & Johnson, Amazon.com Inc

---

### 📊 M&A Analyst (`m_and_a_analyst`)

- **Color:** Purple (`#8b5cf6`)
- **Sources:** SEC, OSHA, EPA
- **Focus:** Material liabilities, pending litigation, financial exposure that could affect deal valuation
- **Query:** `Find material enforcement actions, pending litigation, financial penalties, and unresolved regulatory matters that represent acquisition risk`
- **For:** Pre-acquisition target screening, deal due diligence

**Demo targets:** Boeing Company, Wells Fargo, Meta Platforms

---

### 🌿 ESG Researcher (`esg_researcher`)

- **Color:** Emerald (`#10b981`)
- **Sources:** EPA, OSHA, DOL
- **Focus:** Environmental violations, workplace safety, labor violations, governance failures
- **Query:** `Find environmental violations, workplace safety incidents, labor violations, and governance failures relevant to ESG assessment`
- **For:** ESG scoring, sustainable investment screening, CSR reporting

**Demo targets:** ExxonMobil, Tyson Foods, Dow Chemical

---

### ⚖️ Legal Counsel (`legal_counsel`)

- **Color:** Amber (`#f59e0b`)
- **Sources:** SEC, FDA, OSHA
- **Focus:** Active litigation, case status, appeal history, settlement amounts
- **Query:** `Find all enforcement actions with case status details, appeal history, settlement amounts, and ongoing litigation matters`
- **For:** Litigation risk assessment, opposing party research, precedent mapping

**Demo targets:** Purdue Pharma, Volkswagen, Theranos

---

### 🔍 Investigative Journalist (`investigative_journalist`)

- **Color:** Red (`#ef4444`)
- **Sources:** All 5
- **Focus:** Patterns of repeat violations, escalating penalties, whistleblower complaints
- **Query:** `Find all violations, enforcement actions, repeat offenses, escalating penalties, whistleblower complaints, and patterns of non-compliance`
- **For:** Deep investigative research, pattern-of-conduct stories

**Demo targets:** 3M Company, Uber Technologies, Facebook

---

### 🏭 Supply Chain Auditor (`supply_chain_auditor`)

- **Color:** Cyan (`#06b6d4`)
- **Sources:** OSHA, EPA, DOL
- **Focus:** Factory safety, environmental compliance, labor standards
- **Query:** `Find workplace safety violations, environmental compliance issues, and labor practice violations related to manufacturing and supply chain operations`
- **For:** Vendor risk assessment, supplier audits, manufacturing due diligence

**Demo targets:** Foxconn, Smithfield Foods, Dollar Tree

---

## Persona Data Model

```python
class DemoTarget(BaseModel):
    name: str                         # "Tesla Inc"
    description: str                  # "Electric vehicle manufacturer — OSHA, SEC..."
    query_override: Optional[str]     # Override default query for this specific target

class Persona(BaseModel):
    id: str                           # "compliance_officer"
    label: str                        # "Compliance Officer"
    icon: str                         # "🛡️"
    description: str                  # Longer description
    color: str                        # CSS hex color for UI cards
    default_sources: List[str]        # ["us_osha", "us_fda", ...]
    default_query: str                # Research query template
    focus_areas: List[str]            # UI badges e.g. ["Enforcement Actions", ...]
    demo_targets: List[DemoTarget]    # Pre-built example targets
```

---

## How Personas Apply to a Scan

When a scan is submitted with a `persona_id`:

```python
# In routers/scans.py _run_scan_background()
persona = get_persona(request.persona_id)
if persona:
    if not request.sources:
        request.sources = persona.default_sources   # use persona sources
    if request.query == "regulatory violations and enforcement actions":
        request.query = f"{persona.default_query} for {{target}}"
```

Personas are **advisory**: if the user explicitly provides `sources` or `query`, those override the persona defaults.

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/personas` | List all personas |
| `GET /api/personas/{id}` | Get single persona |

---

## Extending Personas

Add a new persona in `src/api/schemas/persona.py`:

```python
PERSONAS.append(Persona(
    id="risk_manager",
    label="Risk Manager",
    icon="📈",
    description="Enterprise-wide risk aggregation across all regulatory bodies.",
    color="#6366f1",
    default_sources=["us_osha", "us_sec", "us_epa", "us_dol"],
    default_query="Find all open regulatory matters with financial impact",
    focus_areas=["Open Matters", "Financial Exposure", "Trend Analysis"],
    demo_targets=[
        DemoTarget(name="JPMorgan Chase", description="Banking conglomerate — full regulatory exposure"),
    ],
))
```

No code changes needed elsewhere — the API and UI pick up new personas automatically.
