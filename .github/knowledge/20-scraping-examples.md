# TinyFish Web Agent – Web Scraping Examples

## Basic Scraping

Extract product data from a single product page:

```python
from tinyfish import TinyFish, EventType, RunStatus

client = TinyFish()

with client.agent.stream(
    url="https://scrapeme.live/shop/Bulbasaur/",
    goal="Extract the product name, price, and stock status",
) as stream:
    for event in stream:
        if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
            print("Result:", event.result_json)
```

**Output:**

```json
{
  "name": "Bulbasaur",
  "price": 63,
  "inStock": true
}
```

## Scraping Multiple Items

Extract all products from a category or listing page:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://scrapeme.live/shop/",
    goal="Extract all products on this page. For each product return: name, price, and link",
) as stream:
    for event in stream:
        print(event)
```

**Output:**

```json
{
  "products": [
    { "name": "Bulbasaur", "price": 63, "link": "https://scrapeme.live/shop/Bulbasaur/" },
    { "name": "Ivysaur", "price": 87, "link": "https://scrapeme.live/shop/Ivysaur/" },
    { "name": "Venusaur", "price": 105, "link": "https://scrapeme.live/shop/Venusaur/" }
  ]
}
```

## Pagination Handling

Scrape multiple pages and aggregate results:

```python
from tinyfish import TinyFish, EventType, RunStatus

client = TinyFish()

goal = """
Navigate through all pages of the product listing.
For each page:
1. Extract all product names, prices, and links
2. Click the "Next" button if available
3. Continue until there are no more pages

Return all products as a JSON array with fields: name, price, link
"""

with client.agent.stream(
    url="https://scrapeme.live/shop/",
    goal=goal,
) as stream:
    for event in stream:
        if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
            print("All products:", event.result_json)
```

## Dynamic Content Extraction

Handle JavaScript-rendered content:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/dynamic-page",
    goal="""
    Wait for the dynamic content to load.
    Once loaded, extract the title, description, and all list items.
    Return as JSON.
    """,
) as stream:
    for event in stream:
        print(event)
```

## Text Search and Filtering

Extract specific information based on search criteria:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/search",
    goal="""
    Search for "laptop" using the search bar.
    From the results page, extract all items with price under $1000.
    Return as JSON with fields: name, price, rating, url.
    """,
) as stream:
    for event in stream:
        print(event)
```

## Table Scraping

Extract structured data from HTML tables:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/data-table",
    goal="""
    Find the main data table on this page.
    Extract all rows as JSON.
    Each row should have the following fields: id, name, email, status, date.
    """,
) as stream:
    for event in stream:
        print(event)
```

## Handling Modals and Pop-ups

Deal with common web UI elements:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com",
    goal="""
    If a modal or pop-up appears, close it by clicking the X or "Close" button.
    If a cookie banner appears, accept or dismiss it.
    Then extract the main page content: title, description, and all links.
    Return as JSON.
    """,
) as stream:
    for event in stream:
        print(event)
```

## Structured Data Extraction

Extract and structure data according to a schema:

```python
from tinyfish import TinyFish

client = TinyFish()

schema = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "price": {"type": "number"},
        "rating": {"type": "number"},
        "in_stock": {"type": "boolean"},
        "reviews_count": {"type": "integer"},
        "description": {"type": "string"}
    }
}

with client.agent.stream(
    url="https://example.com/product",
    goal=f"Extract product information matching this schema: {schema}",
) as stream:
    for event in stream:
        print(event)
```

## Best Practices

### 1. Be Specific in Your Goal

Good: "Extract the product name, price, and 'in stock' status"

Worse: "Extract product data"

### 2. Handle Errors Gracefully

```python
from tinyfish import TinyFish, EventType, RunStatus

client = TinyFish()

with client.agent.stream(
    url="https://example.com",
    goal="Extract data",
) as stream:
    for event in stream:
        if event.type == EventType.ERROR:
            print("Error during scraping:", event.error)
        elif event.type == EventType.COMPLETE:
            if event.status == RunStatus.COMPLETED:
                print("Success:", event.result_json)
            else:
                print("Failed:", event.error)
```

### 3. Use Clear Return Format Instructions

Always specify the expected output format:

```python
goal = """
Extract all product information and return as a JSON object with:
- products: array of objects
- each product has: id, name, price, rating, url
"""
```

### 4. Set Reasonable Timeouts

```python
with client.agent.stream(
    url="https://example.com",
    goal="Extract data",
    timeout_seconds=120,  # 2 minutes
) as stream:
    for event in stream:
        print(event)
```

### 5. Log Events for Debugging

```python
import json

with client.agent.stream(
    url="https://example.com",
    goal="Extract data",
) as stream:
    for event in stream:
        print(json.dumps(event.to_dict(), indent=2))
```

## Related

- [Quick Start](./10-quickstart-python.md) – Get started with TinyFish
- [Forms and Authentication](./30-forms-and-auth.md) – Handle login and form submission
- [Stealth Mode and Proxies](./40-stealth-and-proxies.md) – Evade bot detection and route geographically
