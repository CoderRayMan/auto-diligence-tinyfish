# TinyFish Web Agent – Overview

## What is TinyFish Web Agent?

TinyFish Web Agent enables enterprises, builders, and developers to deploy AI agents that navigate real sites, complete real workflows across authenticated systems and dynamic interfaces, and return structured operational intelligence—through a visual platform or API. At scale. Reliably.

## Why TinyFish Web Agent?

### Natural Language Control

Describe tasks in plain English. No CSS selectors or XPath needed. Your agents understand what you want and navigate the web the way humans do.

### Real-Time Streaming

Watch your automation execute live with Server-Sent Events (SSE). Stream events as your agent makes decisions, clicks buttons, fills forms, and extracts data in real time.

### Anti-Detection Browsers

Sites with bot protection? TinyFish includes Stealth mode for anti-bot evasion. Your agents look indistinguishable from normal human users.

### Proxy Support

Route requests through specific geographic locations. Perfect for geo-restricted content or testing regional behavior.

### Authenticated Workflows

Navigate sites that require login, handle session tokens, and maintain state across multi-step processes. Built-in support for complex authentication flows.

### Structured Output

Agents return clean, structured JSON instead of raw HTML or screenshots. Ready to integrate with downstream systems.

## Core Capabilities

- **Agent Streaming**: Real-time Server-Sent Events let you observe agent behavior as it happens
- **Browser Profiles**: Choose between Lite (standard) and Stealth modes for bot protection
- **Proxy Routing**: Geographic routing via ProxyConfig with country code selection
- **Natural Language Goals**: Describe workflows in plain English; agent figures out the implementation
- **Error Handling**: Built-in retry logic and resilience for dynamic, flaky websites
- **Multi-Step Workflows**: Support for login → navigate → form fill → extract across multiple pages

## Getting Started

1. **Sign up** at https://www.tinyfish.ai to get an API key
2. **Read the Quick Start** for Python or JavaScript
3. **Try a basic scraping example** to see streaming in action
4. **Explore advanced features** like stealth mode, proxies, and authenticated workflows

## API Overview

The TinyFish API is accessible via the official Python and JavaScript clients.

### Authentication

Set your API key via environment variable:

```bash
export TINYFISH_API_KEY="your_api_key_here"
```

Or pass it directly to the client:

```python
from tinyfish import TinyFish
client = TinyFish(api_key="your_api_key_here")
```

### Basic Usage Pattern

All TinyFish agent calls follow a streaming pattern:

```python
with client.agent.stream(
    url="https://example.com",
    goal="Extract product information",
    browser_profile=BrowserProfile.LITE,  # optional
    proxy_config=None,  # optional
) as stream:
    for event in stream:
        # Process each streaming event
        print(event)
```

The agent returns events as it executes, culminating in a `COMPLETE` event with structured JSON in `event.result_json`.

## Common Use Cases

- **Web Scraping**: Extract data from tables, listings, and dynamic pages
- **Form Filling**: Automate multi-step forms, applications, and workflows
- **Authentication Handling**: Navigate login flows, session management, and protected content
- **Price Monitoring**: Track prices across competitor sites and alert on changes
- **Regulatory Research**: Extract compliance, enforcement, and filing data from government portals
- **Lead Generation**: Scrape contact info and business data from directories and listings

## Next Steps

- [Quick Start Guide](./10-quickstart-python.md) – Run your first agent in 5 minutes
- [Web Scraping Examples](./20-scraping-examples.md) – Learn scraping patterns and best practices
- [Forms and Authentication](./30-forms-and-auth.md) – Handle complex login flows and multi-step workflows
- [Browser Profiles and Stealth Mode](./40-stealth-and-proxies.md) – Evade bot detection
- [Proxy Configuration](./40-stealth-and-proxies.md) – Route through geographic locations
