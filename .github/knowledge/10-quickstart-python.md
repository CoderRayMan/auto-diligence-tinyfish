# TinyFish Web Agent – Python Quick Start

## Installation

Install the TinyFish Python client:

```bash
pip install tinyfish
```

## Set Your API Key

Export your API key as an environment variable:

```bash
export TINYFISH_API_KEY="your_api_key_here"
```

Or pass it directly when creating the client:

```python
from tinyfish import TinyFish

client = TinyFish(api_key="your_api_key_here")
```

## Your First Agent

Here's the simplest example: extract product information from a web page.

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://scrapeme.live/shop",
    goal="Extract the first 2 product names and prices. Respond in JSON",
) as stream:
    for event in stream:
        print(event)
```

**Output:**

```json
{
  "type": "COMPLETE",
  "status": "COMPLETED",
  "result": {
    "products": [
      { "name": "Laptop Pro", "price": "$1,299", "inStock": true },
      { "name": "Wireless Mouse", "price": "$29", "inStock": true }
    ]
  }
}
```

## Understanding the Streaming API

The `client.agent.stream()` method returns a streaming session. Each event represents a step the agent takes:

- **Event types**: `THINKING`, `ACTION`, `WAIT`, `ERROR`, `COMPLETE`
- **Status**: Information about the current state (`IN_PROGRESS`, `COMPLETED`, `FAILED`)
- **Result**: Structured JSON output when the agent completes

### Processing Events

```python
from tinyfish import TinyFish, EventType, RunStatus

client = TinyFish()

with client.agent.stream(
    url="https://example.com",
    goal="Extract data",
) as stream:
    for event in stream:
        # Only process completion events
        if event.type == EventType.COMPLETE:
            if event.status == RunStatus.COMPLETED:
                print("Success! Result:", event.result_json)
            else:
                print("Failed:", event.error)
```

## Common Patterns

### Extract Data from a Single Page

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/product/12345",
    goal="Extract the product name, price, description, and customer reviews",
) as stream:
    for event in stream:
        if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
            print("Product data:", event.result_json)
```

### Handle Long-Running Tasks

For complex workflows, listen to intermediate events:

```python
from tinyfish import TinyFish, EventType

client = TinyFish()

with client.agent.stream(
    url="https://example.com",
    goal="Navigate to the search page, enter filters, and extract results",
) as stream:
    for event in stream:
        if event.type == EventType.ACTION:
            print(f"Agent action: {event.description}")
        elif event.type == EventType.THINKING:
            print(f"Agent reasoning: {event.description}")
        elif event.type == EventType.ERROR:
            print(f"Error occurred: {event.error}")
        elif event.type == EventType.COMPLETE:
            print("Completed with result:", event.result_json)
```

### Set a Timeout

Limit how long an agent can run:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com",
    goal="Extract all products",
    timeout_seconds=60,  # 1 minute max
) as stream:
    for event in stream:
        print(event)
```

## Key Imports

```python
from tinyfish import (
    TinyFish,           # Main client
    EventType,          # Event type constants
    RunStatus,          # Status constants
    BrowserProfile,     # Browser profile options (LITE, STEALTH)
    ProxyConfig,        # Proxy configuration
    ProxyCountryCode,   # Country code constants
)
```

## Next Steps

- [Web Scraping Examples](./20-scraping-examples.md) – Learn scraping patterns
- [Forms and Authentication](./30-forms-and-auth.md) – Handle login flows
- [Stealth Mode and Proxies](./40-stealth-and-proxies.md) – Evade bot detection
