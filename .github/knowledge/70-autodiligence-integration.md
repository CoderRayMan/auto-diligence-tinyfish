# TinyFish Integration Guide for AutoDiligence

## Adapting TinyFish Patterns to Your AutoDiligence Architecture

This guide maps TinyFish capabilities to the AutoDiligence orchestration patterns outlined in your Phase-wise development plan.

---

## Phase 2–3: Single SiteAgent Integration with TinyFish

### Basic SiteAgent Implementation

Your `SiteAgent` class wraps TinyFish's streaming agent:

```python
from tinyfish import TinyFish, BrowserProfile, ProxyConfig, EventType, RunStatus
import json

class SiteAgent:
    def __init__(self, source, token_vault, filters, run_id):
        self.source = source
        self.token_vault = token_vault
        self.filters = filters
        self.run_id = run_id
        self.client = TinyFish()

    def prepare_goal(self):
        """Render the search goal from template and filters."""
        template = self.source.search_goal_template
        # Simple Jinja2-style substitution
        goal = template.replace("{{filters_json}}", json.dumps(self.filters))
        return goal

    def build_tinyfish_params(self):
        """Build parameters for TinyFish agent.stream()."""
        params = {
            "url": self.source.base_url,
            "goal": self.prepare_goal(),
        }
        
        # Apply browser profile from evasion config
        if self.source.browser_profile == "STEALTH":
            params["browser_profile"] = BrowserProfile.STEALTH
        else:
            params["browser_profile"] = BrowserProfile.LITE
        
        # Apply proxy config
        if self.source.proxy.get("enabled"):
            country = self.source.proxy.get("country", "US")
            params["proxy_config"] = ProxyConfig(
                enabled=True,
                country_code=getattr(ProxyCountryCode, country),
            )
        
        return params

    def run(self):
        """Execute the TinyFish agent and return normalized result."""
        kwargs = self.build_tinyfish_params()
        
        with self.client.agent.stream(**kwargs) as stream:
            for event in stream:
                # Log intermediate events for debugging
                if event.type == EventType.ACTION:
                    print(f"[{self.run_id}] Agent action: {event.description}")
                
                # Process completion event
                if event.type == EventType.COMPLETE:
                    if event.status == RunStatus.COMPLETED:
                        return self.normalize_result(event.result_json)
                    else:
                        raise Exception(f"Agent failed: {event.error}")
        
        raise Exception("Agent did not complete")

    def normalize_result(self, raw_json):
        """Convert TinyFish result to internal schema."""
        normalized = {
            "source_id": self.source.id,
            "run_id": self.run_id,
            "status": "success",
            "data": raw_json,
            "schema": self.source.result_schema,
        }
        return normalized
```

### Example Source Registry Entry (YAML)

```yaml
id: "us_osha"
name: "US OSHA Enforcement Records"
base_url: "https://osha.gov/portal/login"
category: "workplace_safety"

login_flow: "username_password"
needs_2fa: false

search_goal_template: |
  Log into the OSHA portal with the provided credentials.
  Navigate to the enforcement cases search page.
  Search for cases matching these filters: {{filters_json}}
  Extract all matching cases. For each case return:
  - case_id
  - employer_name
  - violation_type
  - severity (serious, willful, repeat)
  - proposed_penalty
  - decision_date
  - status (open, settled, appealed)
  
  Return as JSON array.

result_schema:
  type: "object"
  properties:
    cases:
      type: "array"
      items:
        type: "object"
        properties:
          case_id: { type: "string" }
          employer_name: { type: "string" }
          violation_type: { type: "string" }
          severity: { type: "string" }
          proposed_penalty: { type: "number" }
          decision_date: { type: "string" }
          status: { type: "string" }

browser_profile: "STEALTH"

proxy:
  enabled: true
  country: "US"

rate_limit:
  max_requests_per_minute: 10
  jitter_ms: 500
```

---

## Phase 3–4: Stateful Token Vault Integration

### Token Vault with Session Reuse

The challenge: government sites log out quickly. Solution: TinyFish agents intelligently detect login state.

```python
from datetime import datetime, timedelta
import redis

class TokenVault:
    """Manages login state across Site Agents."""
    
    def __init__(self, redis_url="redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.session_ttl = 1800  # 30 minutes
    
    def get_session(self, source_id: str, user_id: str):
        """Retrieve cached session if still valid."""
        key = f"session:{source_id}:{user_id}"
        data = self.redis.get(key)
        if data:
            session = json.loads(data)
            # Check if session is still fresh
            last_login = datetime.fromisoformat(session["last_login"])
            if (datetime.now() - last_login) < timedelta(seconds=self.session_ttl):
                return session
        return None
    
    def save_session(self, source_id: str, user_id: str, session_data: dict):
        """Store session with TTL."""
        key = f"session:{source_id}:{user_id}"
        session_data["last_login"] = datetime.now().isoformat()
        self.redis.setex(key, self.session_ttl, json.dumps(session_data))
    
    def invalidate_session(self, source_id: str, user_id: str):
        """Mark session as invalid."""
        key = f"session:{source_id}:{user_id}"
        self.redis.delete(key)

class SiteAgentWithStatefulLogin:
    """SiteAgent that reuses login state from vault."""
    
    def __init__(self, source, token_vault, filters, run_id, user_id, credentials):
        self.source = source
        self.token_vault = token_vault
        self.filters = filters
        self.run_id = run_id
        self.user_id = user_id
        self.credentials = credentials  # username, password
        self.client = TinyFish()
    
    def run(self):
        """Run with login state awareness."""
        # Check if valid session exists
        session = self.token_vault.get_session(self.source.id, self.user_id)
        
        if session and session.get("auth_status") == "ok":
            # Reuse existing session: start from search page
            return self.run_research_only()
        else:
            # No valid session: login first, then research
            self.run_login_flow()
            return self.run_research_only()
    
    def run_login_flow(self):
        """Execute login and save session state."""
        login_goal = f"""
        1. Navigate to the login page
        2. Enter username: {self.credentials['username']}
        3. Enter password: {self.credentials['password']}
        4. Click Login button
        5. Verify login succeeded by checking for:
           - Logout button presence
           - User profile menu visibility
           - Dashboard access
        6. Return auth confirmation with these signals
        """
        
        with self.client.agent.stream(
            url=self.source.base_url,
            goal=login_goal,
            browser_profile=BrowserProfile.STEALTH,
        ) as stream:
            for event in stream:
                if event.type == EventType.COMPLETE:
                    if event.status == RunStatus.COMPLETED:
                        # Extract auth signals from result
                        result = event.result_json
                        session_data = {
                            "auth_status": "ok" if result.get("logged_in") else "failed",
                            "observed_signals": result.get("signals", {}),
                        }
                        self.token_vault.save_session(
                            self.source.id, self.user_id, session_data
                        )
                        return
    
    def run_research_only(self):
        """Execute research task, assuming already logged in."""
        research_goal = f"""
        You are already logged into {self.source.name}.
        
        If you see a login page, log in first with credentials provided.
        
        Otherwise, proceed directly to:
        {self.source.search_goal_template.replace("{{filters_json}}", json.dumps(self.filters))}
        """
        
        with self.client.agent.stream(
            url=self.source.base_url,
            goal=research_goal,
            browser_profile=self.get_browser_profile(),
            proxy_config=self.get_proxy_config(),
        ) as stream:
            for event in stream:
                if event.type == EventType.COMPLETE:
                    if event.status == RunStatus.COMPLETED:
                        return self.normalize_result(event.result_json)
```

### Integration with DiligenceManager

```python
class DiligenceManager:
    def __init__(self, source_registry, token_vault, credentials_vault):
        self.source_registry = source_registry
        self.token_vault = token_vault
        self.credentials_vault = credentials_vault

    async def run_request(self, diligence_request):
        """
        Execute diligence request with stateful login management.
        """
        tasks = self._expand_into_search_tasks(diligence_request)
        
        coros = []
        for task in tasks:
            source = self.source_registry.get(task.source_id)
            credentials = self.credentials_vault.get(source.id)
            
            agent = SiteAgentWithStatefulLogin(
                source=source,
                token_vault=self.token_vault,
                filters=task.filters,
                run_id=task.run_id,
                user_id=diligence_request.user_id,
                credentials=credentials,
            )
            coros.append(self._run_agent_safe(agent))
        
        results = await asyncio.gather(*coros, return_exceptions=True)
        return self._aggregate_results(results)
```

---

## Phase 5–6: Deep-Web & Evasion Integration

### Prompt Engineering for Messy Sites

Government portals often have pop-ups, overlays, and dynamic content. Use natural language in TinyFish goals:

```python
# For OSHA with expected pop-ups
search_goal = """
1. If a cookie consent banner appears, click "Accept"
2. If a modal about browser compatibility appears, close it
3. Navigate to the Enforcement Search page
4. Using the search form, search for violations from {{company_name}}
5. Wait for results to load (may show loading spinner)
6. If results don't appear after 10 seconds, try again or use filter form
7. Extract each case: case_id, violation_type, penalty, decision_date
8. Check for pagination; if results span multiple pages, extract all
9. Return all cases as JSON array
"""

# For SEC with authentication challenges
filing_goal = """
1. Log in with provided credentials
2. If 2FA is required, use provided 2FA code: {{2fa_code}}
3. Navigate to company filings
4. Search for filings by company name: {{company_name}}
5. For each filing, extract:
   - Filing type (10-K, 10-Q, 8-K, etc.)
   - Filed date
   - Form link
6. Handle any session timeouts by re-authenticating
7. Return all filings as JSON with metadata
"""
```

### Evasion Profile Application

```python
class EvasionProfile:
    """Centralized evasion strategy per site."""
    
    def __init__(self, config: dict):
        self.browser_profile = BrowserProfile[config.get("browser_profile", "LITE")]
        self.proxy_enabled = config.get("proxy", {}).get("enabled", False)
        self.proxy_country = config.get("proxy", {}).get("country", "US")
        self.rate_limit_rpm = config.get("rate_limit", {}).get("max_requests_per_minute", 20)
        self.jitter_ms = config.get("rate_limit", {}).get("jitter_ms", 0)
        self.retry_count = config.get("retry_policy", {}).get("max_retries", 3)
        self.retry_backoff = config.get("retry_policy", {}).get("backoff_seconds", 2)

class SiteAgentWithEvasion:
    """Applies evasion profile to TinyFish agent."""
    
    def __init__(self, source, token_vault, filters, run_id):
        self.source = source
        self.evasion = EvasionProfile(source.evasion_profile)
        self.token_vault = token_vault
        self.filters = filters
        self.run_id = run_id
        self.client = TinyFish()
    
    def run_with_retry(self):
        """Execute with retry logic and evasion settings."""
        for attempt in range(self.evasion.retry_count):
            try:
                # Add randomized jitter
                if self.evasion.jitter_ms > 0:
                    import random, time
                    jitter = random.randint(0, self.evasion.jitter_ms)
                    time.sleep(jitter / 1000.0)
                
                return self.run()
            
            except Exception as e:
                if attempt < self.evasion.retry_count - 1:
                    wait = self.evasion.retry_backoff ** (attempt + 1)
                    print(f"[{self.run_id}] Retry {attempt + 1} after {wait}s: {e}")
                    time.sleep(wait)
                else:
                    raise
    
    def run(self):
        """Execute with full evasion profile."""
        with self.client.agent.stream(
            url=self.source.base_url,
            goal=self.prepare_goal(),
            browser_profile=self.evasion.browser_profile,
            proxy_config=ProxyConfig(
                enabled=self.evasion.proxy_enabled,
                country_code=ProxyCountryCode[self.evasion.proxy_country],
            ) if self.evasion.proxy_enabled else None,
        ) as stream:
            for event in stream:
                if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
                    return self.normalize_result(event.result_json)
```

---

## Phase 7–8: Scaling & Production Patterns

### Concurrent Agent Execution with Rate Limiting

```python
import asyncio
import time
from collections import defaultdict

class RateLimiter:
    """Per-source rate limiting."""
    
    def __init__(self):
        self.last_run = defaultdict(float)
        self.min_interval = defaultdict(float)
    
    def set_rate_limit(self, source_id: str, requests_per_minute: int):
        self.min_interval[source_id] = 60.0 / requests_per_minute
    
    async def wait(self, source_id: str):
        """Sleep until rate limit allows next request."""
        elapsed = time.time() - self.last_run[source_id]
        wait_time = self.min_interval[source_id] - elapsed
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self.last_run[source_id] = time.time()

class DiligenceManager:
    def __init__(self, source_registry, token_vault, credentials_vault):
        self.source_registry = source_registry
        self.token_vault = token_vault
        self.credentials_vault = credentials_vault
        self.rate_limiter = RateLimiter()
        
        # Configure rate limits per source
        for source in source_registry.all():
            rpm = source.rate_limit.get("max_requests_per_minute", 20)
            self.rate_limiter.set_rate_limit(source.id, rpm)

    async def run_request(self, diligence_request):
        """Execute with rate limiting and proper concurrency."""
        tasks = self._expand_into_search_tasks(diligence_request)
        
        coros = []
        for task in tasks:
            coros.append(self._run_task_with_rate_limit(task))
        
        results = await asyncio.gather(*coros, return_exceptions=True)
        return self._aggregate_results(results)
    
    async def _run_task_with_rate_limit(self, task):
        """Run a single task respecting rate limits."""
        await self.rate_limiter.wait(task.source_id)
        
        source = self.source_registry.get(task.source_id)
        agent = self._create_agent(source, task)
        return await asyncio.to_thread(agent.run)
    
    def _create_agent(self, source, task):
        """Factory for appropriate agent type."""
        if source.login_flow == "none":
            return SiteAgent(source, self.token_vault, task.filters, task.run_id)
        else:
            credentials = self.credentials_vault.get(source.id)
            return SiteAgentWithStatefulLogin(
                source, self.token_vault, task.filters, task.run_id,
                diligence_request.user_id, credentials
            )
```

### Result Aggregation and Risk Scoring

```python
class DiligenceFinding:
    """Normalized finding across sources."""
    
    def __init__(self):
        self.source_id: str
        self.case_id: str
        self.case_type: str  # litigation, regulatory_action, enforcement, etc.
        self.entity_name: str
        self.decision_date: str
        self.penalty_amount: float
        self.severity: str  # minor, moderate, serious, critical
        self.status: str  # open, settled, appealed
        self.description: str
        self.source_url: str

class ResultAggregator:
    """Consolidates and scores diligence findings."""
    
    @staticmethod
    def aggregate(raw_results):
        """Merge results across sources."""
        findings = []
        
        for source_id, result in raw_results.items():
            if result.get("status") == "success":
                # Parse source-specific format into common FindingFormat
                findings.extend(
                    ResultAggregator._parse_findings(source_id, result.get("data", []))
                )
        
        # Deduplicate (same case from multiple sources)
        unique_findings = ResultAggregator._deduplicate(findings)
        
        # Score risk
        scored = [ResultAggregator._score_finding(f) for f in unique_findings]
        
        return sorted(scored, key=lambda f: f["risk_score"], reverse=True)
    
    @staticmethod
    def _score_finding(finding):
        """Assign risk score based on severity, recency, type."""
        base_score = 0
        
        # Severity multiplier
        severity_map = {"critical": 100, "serious": 75, "moderate": 50, "minor": 25}
        base_score += severity_map.get(finding.severity, 50)
        
        # Status adjustment
        if finding.status == "open":
            base_score *= 1.5  # Open cases are riskier
        elif finding.status == "appealed":
            base_score *= 1.2
        
        # Recency (within last 12 months = higher risk)
        # ... date calculation
        
        finding["risk_score"] = min(100, base_score)
        return finding
```

---

## Testing & Validation

### Unit Test for SiteAgent

```python
def test_site_agent_extracts_data():
    """Test that SiteAgent correctly executes TinyFish agent."""
    
    mock_source = Source(
        id="test_osha",
        base_url="https://osha.gov",
        search_goal_template="Search for {{filters_json}}",
        browser_profile="LITE",
        proxy={},
    )
    
    mock_vault = TokenVault()
    filters = {"company": "Acme Corp"}
    
    agent = SiteAgent(mock_source, mock_vault, filters, "test_run_1")
    
    # Mock the TinyFish client
    with patch("tinyfish.TinyFish") as mock_client:
        mock_stream = MagicMock()
        mock_event = MagicMock()
        mock_event.type = EventType.COMPLETE
        mock_event.status = RunStatus.COMPLETED
        mock_event.result_json = {"cases": [{"case_id": "123", "penalty": 50000}]}
        
        mock_stream.__enter__.return_value = iter([mock_event])
        mock_client.return_value.agent.stream.return_value = mock_stream
        
        result = agent.run()
        
        assert result["status"] == "success"
        assert len(result["data"]["cases"]) == 1
        assert result["data"]["cases"][0]["case_id"] == "123"
```

---

## Next Steps

1. **Start with Phase 2**: Implement basic `SiteAgent` wrapping TinyFish
2. **Add Phase 3**: Integrate `TokenVault` for session reuse
3. **Layer Phase 5**: Build prompt templates for your target regulators
4. **Iterate on evasion**: Adjust `browser_profile` and `proxy` config as you test against real sites
5. **Scale with Phase 7**: Add rate limiting and proper async orchestration

TinyFish handles all the hard parts (browser automation, bot detection evasion, streaming). Your job is orchestration, state management, and risk scoring.
