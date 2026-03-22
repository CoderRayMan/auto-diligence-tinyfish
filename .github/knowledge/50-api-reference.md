# TinyFish Web Agent – API Reference

## Client Initialization

### Creating a Client

```python
from tinyfish import TinyFish

# Using environment variable TINYFISH_API_KEY
client = TinyFish()

# Or passing API key directly
client = TinyFish(api_key="your_api_key_here")
```

## Agent Streaming

### Basic Streaming Call

```python
with client.agent.stream(
    url="https://example.com",
    goal="Extract data",
) as stream:
    for event in stream:
        print(event)
```

### Stream Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | str | Yes | The starting URL for the agent |
| `goal` | str | Yes | Natural language description of the task |
| `browser_profile` | BrowserProfile | No | LITE (default) or STEALTH |
| `proxy_config` | ProxyConfig | No | Proxy configuration for geographic routing |
| `timeout_seconds` | int | No | Maximum execution time (default: 300) |

### Complete Example

```python
from tinyfish import TinyFish, BrowserProfile, ProxyConfig, ProxyCountryCode

client = TinyFish()

with client.agent.stream(
    url="https://example.com/search",
    goal="Search for 'laptop' and extract all results with prices",
    browser_profile=BrowserProfile.STEALTH,
    proxy_config=ProxyConfig(
        enabled=True,
        country_code=ProxyCountryCode.US,
    ),
    timeout_seconds=120,
) as stream:
    for event in stream:
        print(event)
```

## Event Types

### EventType Constants

```python
from tinyfish import EventType

EventType.THINKING      # Agent is reasoning about next step
EventType.ACTION        # Agent is performing an action
EventType.WAIT          # Agent is waiting for content to load
EventType.ERROR         # An error occurred
EventType.COMPLETE      # Task is complete
```

### Event Structure

Each event has:

- `type` – EventType constant
- `status` – RunStatus (IN_PROGRESS, COMPLETED, FAILED)
- `description` – Human-readable description
- `result_json` – Structured result (available on COMPLETE events)
- `error` – Error message (available on ERROR events)

### Processing Events

```python
from tinyfish import TinyFish, EventType, RunStatus

client = TinyFish()

with client.agent.stream(
    url="https://example.com",
    goal="Extract data",
) as stream:
    for event in stream:
        print(f"Event Type: {event.type}")
        print(f"Status: {event.status}")
        
        if event.type == EventType.THINKING:
            print(f"Agent thinking: {event.description}")
        
        elif event.type == EventType.ACTION:
            print(f"Agent action: {event.description}")
        
        elif event.type == EventType.WAIT:
            print(f"Agent waiting: {event.description}")
        
        elif event.type == EventType.ERROR:
            print(f"Error: {event.error}")
        
        elif event.type == EventType.COMPLETE:
            if event.status == RunStatus.COMPLETED:
                print(f"Success! Result: {event.result_json}")
            else:
                print(f"Failed: {event.error}")
```

## Browser Profiles

### BrowserProfile

```python
from tinyfish import BrowserProfile

# Standard browser (default)
BrowserProfile.LITE

# Anti-detection stealth browser
BrowserProfile.STEALTH
```

### When to Use Each

- **LITE**: Public sites without bot detection
- **STEALTH**: Protected sites, government portals, or when LITE gets blocked

## Proxy Configuration

### ProxyConfig

```python
from tinyfish import ProxyConfig, ProxyCountryCode

# Disable proxy
proxy = ProxyConfig(enabled=False)

# Enable proxy for specific country
proxy = ProxyConfig(
    enabled=True,
    country_code=ProxyCountryCode.US,
)
```

### ProxyCountryCode

Available country codes:

```python
ProxyCountryCode.US      # United States
ProxyCountryCode.UK      # United Kingdom
ProxyCountryCode.CA      # Canada
ProxyCountryCode.AU      # Australia
ProxyCountryCode.DE      # Germany
ProxyCountryCode.FR      # France
ProxyCountryCode.NL      # Netherlands
ProxyCountryCode.JP      # Japan
ProxyCountryCode.IN      # India
ProxyCountryCode.BR      # Brazil
ProxyCountryCode.MX      # Mexico
ProxyCountryCode.SG      # Singapore
ProxyCountryCode.HK      # Hong Kong
ProxyCountryCode.IT      # Italy
ProxyCountryCode.ES      # Spain
ProxyCountryCode.KR      # South Korea
```

## RunStatus

### Status Constants

```python
from tinyfish import RunStatus

RunStatus.IN_PROGRESS   # Task is still running
RunStatus.COMPLETED     # Task completed successfully
RunStatus.FAILED        # Task failed
RunStatus.TIMEOUT       # Task timed out
```

## Common Patterns

### Basic Scraping

```python
from tinyfish import TinyFish, EventType, RunStatus

client = TinyFish()

with client.agent.stream(
    url="https://example.com",
    goal="Extract product name and price",
) as stream:
    for event in stream:
        if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
            print("Result:", event.result_json)
```

### Form Submission

```python
with client.agent.stream(
    url="https://example.com/form",
    goal="""
    Fill the form with Name: John, Email: john@example.com
    Submit and return the confirmation message
    """,
) as stream:
    for event in stream:
        if event.type == EventType.COMPLETE:
            print("Result:", event.result_json)
```

### Login and Data Extraction

```python
with client.agent.stream(
    url="https://example.com/login",
    goal="""
    Log in with username: user@example.com, password: pass123
    Navigate to dashboard and extract total balance
    """,
    browser_profile=BrowserProfile.STEALTH,
) as stream:
    for event in stream:
        if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
            print("Dashboard data:", event.result_json)
```

### Multi-Step Workflow

```python
with client.agent.stream(
    url="https://example.com",
    goal="""
    1. Click on the search button
    2. Enter 'laptop' in the search box
    3. Filter by price under $1000
    4. Sort by rating
    5. Extract the top 5 results with name, price, and rating
    """,
) as stream:
    for event in stream:
        if event.type == EventType.ACTION:
            print(f"Performing: {event.description}")
        elif event.type == EventType.COMPLETE:
            print("Final results:", event.result_json)
```

### With Error Handling

```python
from tinyfish import TinyFish, EventType, RunStatus

client = TinyFish()

try:
    with client.agent.stream(
        url="https://example.com",
        goal="Extract data",
        timeout_seconds=60,
    ) as stream:
        for event in stream:
            if event.type == EventType.ERROR:
                print(f"Warning: {event.error}")
            elif event.type == EventType.COMPLETE:
                if event.status == RunStatus.COMPLETED:
                    print("Success:", event.result_json)
                else:
                    print("Task failed:", event.error)
except Exception as e:
    print(f"Exception: {e}")
```

## Best Practices

### 1. Always Check Completion Status

```python
if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
    print(event.result_json)
```

### 2. Handle Errors Gracefully

```python
if event.type == EventType.ERROR:
    print(f"Error: {event.error}")
```

### 3. Use Appropriate Browser Profiles

```python
# Start with LITE
with client.agent.stream(url=..., goal=...) as stream:
    # If blocked, retry with STEALTH
```

### 4. Set Reasonable Timeouts

```python
with client.agent.stream(
    url=...,
    goal=...,
    timeout_seconds=120,  # 2 minutes for complex tasks
) as stream:
    ...
```

### 5. Log Events for Debugging

```python
import json

for event in stream:
    print(json.dumps({
        "type": str(event.type),
        "status": str(event.status),
        "description": event.description,
    }, indent=2))
```

## Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| Timeout | Task took too long | Increase `timeout_seconds` or break into smaller tasks |
| Rate Limited | Too many requests | Add delays between requests, use STEALTH mode |
| Blocked | Bot detection triggered | Use `BrowserProfile.STEALTH` or add proxy |
| Not Found | Element doesn't exist | Verify goal is accurate, check if page structure changed |
| Invalid Goal | Goal is too vague | Be specific in natural language description |

## Environment Variables

```bash
export TINYFISH_API_KEY="your_api_key_here"
```

## Rate Limits

Check your account tier for API rate limits. For most tiers:

- ~5-10 concurrent requests
- Adjust based on your account

## Related Resources

- [Quick Start](./10-quickstart-python.md) – Get started
- [Web Scraping Examples](./20-scraping-examples.md) – Scraping patterns
- [Forms and Authentication](./30-forms-and-auth.md) – Complex workflows
- [Stealth Mode and Proxies](./40-stealth-and-proxies.md) – Bot evasion
