# AutoDiligence — Risk Scoring Algorithm

The `ResultAggregator` in `src/utils/risk_scorer.py` normalises raw TinyFish output into ranked `DiligenceFinding` objects and computes an aggregate 0–100 risk score.

---

## 1. Finding Normalisation

### Input

Raw JSON returned by TinyFish `result_json`, expected shape:

```json
{
  "cases": [
    {
      "case_id": "2023-OSHA-0042",
      "employer_name": "Tesla Inc",
      "violation_type": "serious",
      "proposed_penalty": "145000",
      "decision_date": "2023-07-15",
      "status": "settled",
      "jurisdiction": "California DOSH",
      "description": "Failure to provide adequate machine guarding.",
      "source_url": "https://www.osha.gov/..."
    }
  ]
}
```

### Penalty Parsing

`_parse_penalty(raw)` handles all common formats:

| Input | Parsed |
|---|---|
| `145000` (int/float) | `145000.0` |
| `"$145,000"` | `145000.0` |
| `"1.5M"` | `1500000.0` |
| `"450k"` | `450000.0` |
| `null` / `""` | `0.0` |

### Severity Classification

`_classify_severity(violation_type, penalty, status)` applies keyword matching + penalty thresholds:

```
violation_type.lower() contains:
  "willful" | "repeat" | "fraud" | "criminal" | "egregious" | "reckless" | "knowingly" | "felony"
  OR penalty >= $500,000
→ critical

  "serious" | "warning letter" | "consent order" | "cease and desist" | "enforcement" | "violation"
  OR penalty >= $100,000
→ high

  "moderate" | "citation" | "notice" | "corrective"
  OR penalty >= $10,000
→ medium

  (default)
→ low
```

### `DiligenceFinding` Dataclass

```python
@dataclass
class DiligenceFinding:
    finding_id: str       # "{source_id}_{case_id}"
    source_id: str        # "us_osha"
    case_id: str
    case_type: str        # same as source_id
    entity_name: str
    violation_type: str
    decision_date: str    # ISO string as-is from TinyFish
    penalty_amount: float # parsed USD value
    severity: str         # "critical" | "high" | "medium" | "low"
    status: str           # "open" | "settled" | "closed" | "appealed"
    description: str
    source_url: str
    jurisdiction: str
    raw: Dict             # original case dict (for debugging)
```

---

## 2. Multi-Source Aggregation

`ResultAggregator.aggregate_all(raw_results)` merges findings from all sources:

```python
raw_results = {
    "us_osha": {"status": "completed", "cases": [...]},
    "us_sec":  {"status": "completed", "cases": [...]},
    "us_fda":  {"status": "failed", "cases": []},
}
```

1. Filters to sources where `status in ("completed", "success")`
2. Calls `normalize(source_id, result)` per source
3. Merges all into a single list
4. Sorts by:
   - Primary: severity rank (`critical=0, high=1, medium=2, low=3`)
   - Secondary: penalty amount descending (higher penalty first within same severity)

---

## 3. Risk Score Computation

`ResultAggregator.compute_risk_score(findings)` returns:

```python
{
  "score": 42,           # 0–100 integer
  "label": "High Risk",  # human label
  "breakdown": {         # count per severity bucket
    "critical": 1,
    "high": 8,
    "medium": 5,
    "low": 3
  }
}
```

### Scoring Formula

```
weights = { critical: 30, high: 15, medium: 5, low: 1 }
open_multiplier = 1.5   # open cases are 50% more risky than closed/settled

raw_score = Σ (weight[severity] × open_multiplier_if_open)
score = min(100, int(raw_score))
```

### Example Calculation

| Finding | Severity | Status | Weight | Multiplier | Points |
|---|---|---|---|---|---|
| OSHA willful violation | critical | open | 30 | 1.5 | 45 |
| SEC insider trading | high | settled | 15 | 1.0 | 15 |
| OSHA serious ×4 | high | open | 15×4 | 1.5 | 90 |
| FDA warning letter | medium | closed | 5 | 1.0 | 5 |
| DOL wage citation | low | closed | 1 | 1.0 | 1 |
| **Total** | | | | | **min(156, 100) = 100** |

### Risk Labels

| Score Range | Label |
|---|---|
| 70–100 | Critical Risk |
| 40–69 | High Risk |
| 15–39 | Medium Risk |
| 1–14 | Low Risk |
| 0 | Clean |

---

## 4. Integration with API

The scan router calls risk scoring after all agents complete:

```python
# In routers/scans.py _run_scan_background()
diligence_findings = ResultAggregator.aggregate_all(all_raw)
risk = ResultAggregator.compute_risk_score(diligence_findings)

await scan_store.update(
    scan_id,
    risk_score=risk["score"],          # 0–100
    risk_label=risk["label"],          # "High Risk"
    findings_count=len(diligence_findings),
)
```

---

## 5. Tuning the Scorer

To adjust risk sensitivity, modify the constants in `risk_scorer.py`:

```python
_CRITICAL_KEYWORDS = {
    "willful", "repeat", "fraud", "criminal", "egregious",
    "reckless", "knowingly", "felony",
    # add: "debarred", "suspended"
}

weights = {"critical": 30, "high": 15, "medium": 5, "low": 1}
# Increase critical weight to make the system more sensitive to critical findings

open_mult = 1.5
# Increase to penalise open cases more heavily
```

To add gravity to specific sources (e.g., SEC findings are inherently more material):

```python
source_weight_multiplier = {
    "us_sec": 1.5,
    "us_osha": 1.0,
    "us_fda": 1.2,
}
# Apply in compute_risk_score() when processing each finding
```
