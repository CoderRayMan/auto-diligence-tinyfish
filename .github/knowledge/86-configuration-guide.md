# AutoDiligence — Configuration Guide

---

## 1. Environment Variables

Create a `.env` file in the project root:

```bash
# Required
TINYFISH_API_KEY=sk-tinyfish-...

# Optional — defaults shown
CORS_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:3000

# Optional — for distributed TokenVault
REDIS_URL=redis://localhost:6379/0
```

### `TINYFISH_API_KEY`

Obtain from [https://www.tinyfish.ai](https://www.tinyfish.ai). The key is read by the TinyFish SDK (`TinyFish()` constructor auto-reads `TINYFISH_API_KEY` from the environment).

**Without this key, all agent runs will fail with `AuthenticationError`.**

### `CORS_ORIGINS`

Comma-separated list of allowed origins for the FastAPI CORS middleware. In production, set this to your frontend domain.

### `REDIS_URL`

If set and a Redis connection is available, `TokenVault` uses Redis for distributed session storage. Otherwise falls back to in-memory (per-process, lost on restart).

---

## 2. `config/sources.yaml` — Source Registry

Defines every regulatory data source the system can query.

### Schema

```yaml
sources:
  - id: "us_osha"                          # unique source ID used throughout the system
    name: "US OSHA Enforcement Records"    # human label
    base_url: "https://www.osha.gov/enforcement"  # URL passed to TinyFish
    category: "workplace_safety"           # logical grouping (used in UI/reporting)
    login_flow: "none"                     # "none" | "username_password"
    browser_profile: "STEALTH"             # "LITE" | "STEALTH"
    proxy:
      enabled: false
      country: "US"
    rate_limit:
      max_requests_per_minute: 5           # respected by BaseAgent jitter
      jitter_ms: 500                       # random delay 0–500ms before each attempt
    retry_policy:
      max_retries: 3
      backoff_seconds: 2
    search_goal_template: |
      Navigate to the OSHA enforcement search page.
      Search for inspection and enforcement records for company: {{company_name}}.
      ...
      Return all results as a JSON array under the key "cases".
```

### Currently Configured Sources

| ID | Name | Category | Profile |
|---|---|---|---|
| `us_osha` | US OSHA Enforcement Records | workplace_safety | STEALTH |
| `us_fda` | FDA Warning Letters & Enforcement | fda_enforcement | LITE |
| `us_sec` | SEC Enforcement Actions | financial_regulatory | LITE |
| `us_dol` | Department of Labor Wage & Hour | labor_violations | LITE |
| `us_epa` | EPA Environmental Enforcement | environmental | LITE |

### Goal Template Variables

Templates use `{{double_brace}}` placeholders rendered at runtime:

| Placeholder | Filled with |
|---|---|
| `{{company_name}}` | `ScanRequest.target` |
| `{{date_from}}` | `ScanRequest.date_from` or `"2020-01-01"` |
| `{{date_to}}` | `ScanRequest.date_to` or today |
| `{{filters_json}}` | Full filters dict as JSON |

---

## 3. `config/evasion_profiles.yaml` — Browser Evasion Profiles

Defines named anti-detection configurations assigned per source.

### Profiles

#### `standard`
```yaml
browser_profile: LITE
proxy.enabled: false
rate_limit.max_requests_per_minute: 20
rate_limit.jitter_ms: 0
retry_policy.max_retries: 2
retry_policy.backoff_seconds: 1
```
Use for: public APIs, simple public sites, low-risk scraping.

#### `stealth`
```yaml
browser_profile: STEALTH
proxy.enabled: false
rate_limit.max_requests_per_minute: 5
rate_limit.jitter_ms: 800
retry_policy.max_retries: 3
retry_policy.backoff_seconds: 3
```
Use for: government portals with Cloudflare or basic bot detection. **Default for OSHA.**

#### `stealth_proxied`
```yaml
browser_profile: STEALTH
proxy.enabled: true
proxy.country: "US"
proxy.type: "residential"
rate_limit.max_requests_per_minute: 3
rate_limit.jitter_ms: 1500
retry_policy.max_retries: 4
retry_policy.backoff_seconds: 5
```
Use for: sites with IP-based rate limiting or geo-restrictions.

#### `high_security`
```yaml
browser_profile: STEALTH
proxy.enabled: true
proxy.type: "residential"
rate_limit.max_requests_per_minute: 2
rate_limit.jitter_ms: 2000
retry_policy.max_retries: 5
retry_policy.backoff_seconds: 8
```
Use for: aggressive bot detection (DataDome, PerimeterX, etc.).

### Source-to-Profile Mapping

```yaml
source_profile_mapping:
  us_osha: stealth
  us_fda: standard
  us_sec: standard
  us_dol: standard
  us_epa: standard
```

> **Note:** The current `BaseAgent` implementation reads `browser_profile` and `rate_limit`/`retry_policy` directly from `SourceConfig` (loaded from `sources.yaml`). The `evasion_profiles.yaml` is the declarative reference and can be used to override at runtime by merging profile values over source config in `AgentFactory._create_agent()`.

---

## 4. Adding a New Regulatory Source

**Step 1 — Add to `config/sources.yaml`:**

```yaml
  - id: "us_ftc"
    name: "FTC Enforcement Actions"
    base_url: "https://www.ftc.gov/enforcement/cases-proceedings"
    category: "consumer_protection"
    login_flow: "none"
    browser_profile: "LITE"
    proxy:
      enabled: false
    rate_limit:
      max_requests_per_minute: 10
      jitter_ms: 200
    retry_policy:
      max_retries: 3
      backoff_seconds: 2
    search_goal_template: |
      Navigate to the FTC enforcement actions page.
      Search for cases involving: {{company_name}}.
      For each case extract: case_id, employer_name, violation_type,
      proposed_penalty, decision_date, status, jurisdiction, description, source_url.
      Return {{"cases": [...]}}
```

**Step 2 — Create `src/sources/ftc_agent.py`:**

```python
from .base import BaseAgent, SourceConfig
from typing import Any, Dict, List

class FtcAgent(BaseAgent):
    def _build_goal(self, target: str, query: str) -> str:
        return f"""
        Navigate to the FTC enforcement actions page at {self.source.base_url}.
        Search for enforcement actions involving: "{target}".
        Context: {query}
        For each action extract: case_id, employer_name, violation_type,
        proposed_penalty (numeric USD), decision_date (YYYY-MM-DD),
        status (settled|litigated|ongoing|closed), jurisdiction, description, source_url.
        Return {{"cases": [...]}}
        """

    def _normalize_result(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        cases = raw_json.get("cases", [])
        normalized = []
        for case in cases:
            if not isinstance(case, dict):
                continue
            normalized.append({
                "case_id": case.get("case_id", ""),
                "employer_name": case.get("employer_name", ""),
                "violation_type": case.get("violation_type", "Consumer Protection Violation"),
                "proposed_penalty": case.get("proposed_penalty", 0),
                "decision_date": case.get("decision_date", ""),
                "status": (case.get("status") or "unknown").lower(),
                "jurisdiction": "US Federal (FTC)",
                "description": case.get("description", ""),
                "source_url": case.get("source_url", self.source.base_url),
                "source": "FTC",
            })
        return normalized
```

**Step 3 — Register in `src/agent_factory.py`:**

```python
from .sources.ftc_agent import FtcAgent

_AGENT_REGISTRY: Dict[str, type] = {
    "us_osha": OshaAgent,
    "us_fda":  FdaAgent,
    "us_sec":  SecAgent,
    "us_ftc":  FtcAgent,  # ← add here
}
```

**Step 4 — Add to `NewScan.tsx` source list (optional UI update):**

```typescript
const ALL_SOURCES = [
  ...
  { id: "us_ftc", label: "FTC", description: "Consumer protection enforcement" },
];
```

That's it. The new source will appear in the scan form, be available for personas, and produce findings automatically.
