# TinyFish Web Agent – Real-World Recipes from the Cookbook

> This document covers practical, production-ready patterns from the official TinyFish Cookbook — open-source examples of agents solving real problems.

## 1. Brand Sentiment Analysis

Monitor your brand mentions and sentiment across multiple sites simultaneously.

### Use Case

- Track how your brand is talked about across review sites, social media, and news outlets
- Detect negative sentiment early
- Quantify brand perception over time

### Implementation Pattern

```python
from tinyfish import TinyFish, BrowserProfile, ProxyConfig, ProxyCountryCode
import asyncio

sites_to_monitor = [
    {
        "site": "ProductHunt",
        "url": "https://producthunt.com/search?q=YourBrand",
        "goal": "Find all mentions of 'YourBrand'. Extract sentiment (positive/negative/neutral), rating, and comment text."
    },
    {
        "site": "Trustpilot",
        "url": "https://trustpilot.com/search?query=YourBrand",
        "goal": "Extract all reviews for YourBrand. Get rating (1-5), review text, and date."
    },
    {
        "site": "Twitter",
        "url": "https://twitter.com/search?q=YourBrand",
        "goal": "Find recent tweets mentioning 'YourBrand'. Extract text, engagement (likes, retweets), and date."
    },
]

async def run_sentiment_batch():
    client = TinyFish()
    tasks = []
    
    for item in sites_to_monitor:
        with client.agent.stream(
            url=item["url"],
            goal=item["goal"],
            browser_profile=BrowserProfile.LITE,
        ) as stream:
            for event in stream:
                print(f"{item['site']}: {event}")

asyncio.run(run_sentiment_batch())
```

### Key Patterns

- **Multi-site monitoring**: Spin up agents for each site in parallel
- **Structured sentiment extraction**: Normalize sentiment across different platforms
- **Time-series tracking**: Run daily to build sentiment trends
- **Evasion consideration**: Use appropriate browser profile per site (news sites usually LITE, Twitter might need STEALTH)

---

## 2. Price Matching and Competitor Tracking

Monitor competitor pricing in real-time across multiple retailers.

### Use Case

- Detect when competitors change prices
- Find arbitrage opportunities
- Verify your pricing strategy
- Alert sales team to price drops

### Implementation Pattern

```python
from tinyfish import TinyFish, BrowserProfile, ProxyConfig, ProxyCountryCode
import json
import time

competitors = [
    {
        "name": "Amazon",
        "url": "https://amazon.com/s?k=laptop",
        "goal": "Extract all laptop listings. For each: product name, price, rating, seller, in-stock status.",
    },
    {
        "name": "BestBuy",
        "url": "https://bestbuy.com/site/searchpage.jsp?st=laptop",
        "goal": "Extract laptop listings. For each: product name, current price, original price, discount %, in stock?",
    },
    {
        "name": "Newegg",
        "url": "https://newegg.com/pl/search?q=laptop",
        "goal": "Extract laptop products. For each: name, price, shipping cost, ratings count.",
    },
]

def track_prices():
    client = TinyFish()
    results = {}
    
    for competitor in competitors:
        with client.agent.stream(
            url=competitor["url"],
            goal=competitor["goal"],
            browser_profile=BrowserProfile.STEALTH,  # Most retailers have bot detection
            proxy_config=ProxyConfig(enabled=True, country_code=ProxyCountryCode.US),
        ) as stream:
            for event in stream:
                if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
                    results[competitor["name"]] = event.result_json
                    print(f"{competitor['name']} prices updated")
        
        time.sleep(2)  # Respectful delay between requests
    
    return results

# Run daily and store in time-series DB
prices = track_prices()
print(json.dumps(prices, indent=2))
```

### Key Patterns

- **Rate-limited requests**: Add delays between competitor site calls
- **Bot evasion**: Use STEALTH mode for retail sites
- **Geographic proxies**: Use country-specific proxies if prices vary by region
- **Time-series storage**: Store results with timestamps for trend analysis
- **Alert generation**: Compare current vs. previous prices, trigger alerts on significant changes

---

## 3. Sales Opportunity Discovery

Automatically find and extract lead information from multiple sources.

### Use Case

- Find companies matching your ideal customer profile
- Extract contact information and decision-makers
- Identify industry vertical and company size
- Build prospecting lists automatically

### Implementation Pattern

```python
from tinyfish import TinyFish, BrowserProfile

# Search multiple sources for potential customers
sources = [
    {
        "source": "LinkedIn Companies",
        "url": "https://linkedin.com/search/results/companies/?keywords=SaaS&locationUrn=101165590",
        "goal": """
        Extract all company listings. For each company, extract:
        - Company name
        - Industry
        - Company size (number of employees)
        - Founded year
        - Location
        - LinkedIn profile URL
        Order by most recent companies first.
        """
    },
    {
        "source": "ZoomInfo",
        "url": "https://zoominfo.com/search?q=B2B+SaaS+companies",
        "goal": """
        Find B2B SaaS companies. Extract:
        - Company name
        - Annual revenue
        - Number of employees
        - Industry classification
        - Headquarters location
        - Key executives (names and titles)
        - Contact email/phone
        """
    },
    {
        "source": "Inc 5000",
        "url": "https://www.inc.com/inc5000/2024",
        "goal": """
        Extract the Inc 5000 list. For each company:
        - Company name
        - Rank
        - Revenue
        - Growth percentage
        - Founder names
        - Industry
        - Location
        """
    }
]

def discover_opportunities():
    client = TinyFish()
    all_leads = []
    
    for source in sources:
        with client.agent.stream(
            url=source["url"],
            goal=source["goal"],
            browser_profile=BrowserProfile.STEALTH,
        ) as stream:
            for event in stream:
                if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
                    companies = event.result_json
                    # Enrich each lead
                    for company in companies:
                        company["source"] = source["source"]
                        company["discovered_date"] = datetime.now().isoformat()
                    all_leads.extend(companies)
    
    return all_leads

leads = discover_opportunities()
print(f"Found {len(leads)} potential customers")
```

### Key Patterns

- **Multi-source enrichment**: Combine data from LinkedIn, ZoomInfo, Inc5000, etc.
- **Parallel execution**: All sources queried simultaneously
- **Structured enrichment**: Normalize company data across sources
- **Deduplication**: Match and merge leads appearing in multiple sources
- **Lead scoring**: Apply scoring rules (e.g., higher score for funded startups, growing companies)

---

## 4. Daily Briefing Generator

Aggregate news, weather, and insights across multiple sources into a daily briefing.

### Use Case

- Executives get a single daily briefing combining news, market data, and internal metrics
- Automated intelligence digest delivered each morning
- Reduces time spent reading multiple sources

### Implementation Pattern

```python
from tinyfish import TinyFish, EventType, RunStatus
from datetime import datetime

briefing_sources = [
    {
        "section": "Tech News",
        "url": "https://techcrunch.com",
        "goal": "Extract top 5 tech news stories. For each: headline, summary (2-3 sentences), link, date published.",
    },
    {
        "section": "Market Data",
        "url": "https://finance.yahoo.com",
        "goal": "Extract current market indices: S&P 500, Nasdaq, Dow Jones. For each: ticker, current price, change %, change amount.",
    },
    {
        "section": "Weather",
        "url": "https://weather.com/weather/today",
        "goal": "Extract today's weather forecast. Include: temperature, condition, humidity, wind speed, UV index.",
    },
    {
        "section": "Industry Alerts",
        "url": "https://example.com/industry-news",
        "goal": "Find latest news for our industry (SaaS). Extract: headline, source, relevance to our company.",
    },
]

def generate_daily_briefing():
    client = TinyFish()
    briefing = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "sections": {}
    }
    
    for source in briefing_sources:
        with client.agent.stream(
            url=source["url"],
            goal=source["goal"],
        ) as stream:
            for event in stream:
                if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
                    briefing["sections"][source["section"]] = event.result_json
    
    return briefing

# Generate and email briefing
briefing = generate_daily_briefing()
# Format as HTML and email to executives
send_email(to=["ceo@company.com"], subject="Daily Briefing", body=format_briefing(briefing))
```

### Key Patterns

- **Multiple data sources**: News, weather, markets, internal data
- **Scheduled execution**: Run daily at 6 AM via cron or scheduler
- **HTML formatting**: Convert to pretty email template
- **Personalization**: Different briefings for different roles/interests
- **Caching**: Cache non-real-time data (weather) to reduce API calls

---

## 5. Event and Stay Search

Find events and accommodations matching user criteria across multiple platforms.

### Use Case

- User searches for "tech conferences in NYC March 2026"
- System searches EventBrite, conference sites, hotels, Airbnb, flights
- Returns consolidated list sorted by value/relevance

### Implementation Pattern

```python
from tinyfish import TinyFish, BrowserProfile, EventType, RunStatus

def search_events_and_stays(event_query, location, dates):
    """
    Comprehensive search across events, hotels, and flights.
    """
    client = TinyFish()
    
    search_tasks = [
        {
            "type": "events",
            "url": "https://www.eventbrite.com/d/" + location,
            "goal": f"""
            Search for events matching: {event_query}
            For each event: title, date, time, location, ticket price, link
            """,
        },
        {
            "type": "hotels",
            "url": "https://www.booking.com/searchresults.en.html",
            "goal": f"""
            Search for hotels in {location} for dates {dates}
            For each hotel: name, rating, price per night, amenities, booking link
            """,
        },
        {
            "type": "flights",
            "url": "https://www.kayak.com/flights",
            "goal": f"""
            Search for flights to {location} for {dates}
            For each flight: airline, departure/arrival times, price, stops
            """,
        },
        {
            "type": "airbnb",
            "url": "https://www.airbnb.com",
            "goal": f"""
            Search for Airbnb listings in {location} for {dates}
            For each listing: title, price per night, rating, number of guests
            """,
        },
    ]
    
    results = {}
    
    for task in search_tasks:
        with client.agent.stream(
            url=task["url"],
            goal=task["goal"],
            browser_profile=BrowserProfile.LITE,
        ) as stream:
            for event in stream:
                if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
                    results[task["type"]] = event.result_json
    
    return results

# Usage
trip_data = search_events_and_stays(
    event_query="Tech conferences",
    location="New York City",
    dates="March 15-17, 2026"
)
print(trip_data)
```

### Key Patterns

- **Cross-domain search**: Events, accommodations, transport in parallel
- **Result consolidation**: Merge results into single trip plan
- **Cost calculation**: Total trip cost across all components
- **Filtering and sorting**: Sort by total cost, distance, ratings

---

## 6. Open Box Deal Finder

Monitor 8+ retailers simultaneously for open-box/refurbished deals.

### Use Case

- Find open-box electronics that are deeply discounted
- Alert when specific products are available
- Compare prices across retailers
- Track deal history

### Implementation Pattern

```python
from tinyfish import TinyFish, BrowserProfile, ProxyConfig, ProxyCountryCode
import time

retailers = [
    {"name": "Best Buy", "url": "https://bestbuy.com/site/searchpage.jsp?st=open+box"},
    {"name": "Newegg", "url": "https://newegg.com/pl/search?q=open+box"},
    {"name": "Micro Center", "url": "https://microcenter.com/search/search_results.aspx?searchterm=open+box"},
    {"name": "Amazon", "url": "https://amazon.com/s?k=open+box"},
    {"name": "Costco", "url": "https://costco.com/open-box.html"},
    {"name": "Walmart", "url": "https://walmart.com/search/?q=open+box"},
    {"name": "Target", "url": "https://target.com/s?searchTerm=open+box"},
    {"name": "Adorama", "url": "https://adorama.com/n/search/open-box"},
]

def find_open_box_deals():
    client = TinyFish()
    all_deals = []
    
    for retailer in retailers:
        with client.agent.stream(
            url=retailer["url"],
            goal="""
            Find all open-box and refurbished items. For each:
            - Product name and category
            - Original price
            - Discounted price
            - Discount percentage
            - Condition (open box, refurbished, etc.)
            - In stock? (yes/no)
            - SKU or product ID
            """,
            browser_profile=BrowserProfile.STEALTH,
            proxy_config=ProxyConfig(enabled=True, country_code=ProxyCountryCode.US),
        ) as stream:
            for event in stream:
                if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
                    deals = event.result_json
                    for deal in deals:
                        deal["retailer"] = retailer["name"]
                    all_deals.extend(deals)
        
        time.sleep(1)  # Respectful throttling
    
    # Sort by discount percentage
    all_deals.sort(key=lambda x: x.get("discount_percentage", 0), reverse=True)
    return all_deals

deals = find_open_box_deals()
print(f"Found {len(deals)} open-box deals")
for deal in deals[:10]:  # Show top 10
    print(f"{deal['retailer']}: {deal['product_name']} - {deal['discount_percentage']}% off")
```

### Key Patterns

- **8+ parallel retailers**: Simultaneous monitoring across all major retailers
- **Stealth browsing**: Open-box sections often heavily protected
- **Structured deal extraction**: Normalize price, discount %, condition across retailers
- **Alert generation**: Email when specific products found or discount >50%
- **Deal aggregation**: Consolidate across retailers into single ranked list

---

## 7. Loan Comparison Engine

Help users find the best loan terms across multiple lenders.

### Use Case

- User enters loan amount and credit profile
- System checks rates from 10+ lenders simultaneously
- Returns comparison with best rate, terms, and next steps

### Implementation Pattern

```python
from tinyfish import TinyFish, EventType, RunStatus

lenders = [
    {"name": "LendingClub", "url": "https://lendingclub.com/loans"},
    {"name": "SoFi", "url": "https://sofi.com/personal-loans"},
    {"name": "Upstart", "url": "https://upstart.com"},
    {"name": "Better", "url": "https://better.com/personal-loans"},
    {"name": "OppFi", "url": "https://oppfi.com/loans"},
]

def compare_loan_rates(amount, credit_score, term_months):
    """
    Compare loan rates from multiple lenders.
    """
    client = TinyFish()
    rates = []
    
    for lender in lenders:
        with client.agent.stream(
            url=lender["url"],
            goal=f"""
            Get a loan quote for:
            - Loan amount: ${amount}
            - Credit score: {credit_score}
            - Term: {term_months} months
            
            Extract:
            - APR (annual percentage rate)
            - Monthly payment
            - Total interest paid
            - Fees
            - Required credit score minimum
            - Application link
            """,
            browser_profile=BrowserProfile.LITE,
        ) as stream:
            for event in stream:
                if event.type == EventType.COMPLETE and event.status == RunStatus.COMPLETED:
                    quote = event.result_json
                    quote["lender"] = lender["name"]
                    rates.append(quote)
    
    # Sort by APR (lowest first)
    rates.sort(key=lambda x: x.get("apr", float('inf')))
    return rates

# Usage
quotes = compare_loan_rates(amount=25000, credit_score=750, term_months=36)
print("Best loan rates:")
for quote in quotes[:3]:
    print(f"{quote['lender']}: {quote['apr']}% APR, ${quote['monthly_payment']}/month")
```

### Key Patterns

- **Real-time rate comparison**: Query multiple lenders in parallel
- **Standardized comparison**: Normalize APR, fees, terms across lenders
- **Filtering by eligibility**: Pre-filter lenders by credit score requirement
- **Cost breakdown**: Show principal, interest, fees separately
- **Application funnel**: Link directly to application for best rates

---

## 8. Port Congestion Tracker

Monitor shipping port congestion across international ports in real-time.

### Use Case

- Supply chain managers track port wait times
- Alert when congestion reaches critical levels
- Plan shipments to avoid congestion windows
- Understand global logistics patterns

### Implementation Pattern

```python
from tinyfish import TinyFish, ProxyConfig, ProxyCountryCode

ports_to_track = [
    {
        "port": "Port of Shanghai",
        "country": ProxyCountryCode.CN,
        "url": "https://www.portshanghai.com.cn",
        "goal": "Extract current port congestion status, wait times, and vessel queue length",
    },
    {
        "port": "Port of Singapore",
        "country": ProxyCountryCode.SG,
        "url": "https://www.singaporeport.com.sg",
        "goal": "Get real-time congestion data, number of vessels waiting, average wait time",
    },
    {
        "port": "Los Angeles Port",
        "country": ProxyCountryCode.US,
        "url": "https://www.portoflosangeles.org",
        "goal": "Extract port congestion metrics, vessel arrivals/departures, berth availability",
    },
    {
        "port": "Rotterdam Port",
        "country": ProxyCountryCode.NL,
        "url": "https://www.portofrotterdam.com",
        "goal": "Get container vessel queue length, average wait time, current utilization %",
    },
]

def track_port_congestion():
    client = TinyFish()
    congestion_data = {}
    
    for port_info in ports_to_track:
        with client.agent.stream(
            url=port_info["url"],
            goal=port_info["goal"],
            proxy_config=ProxyConfig(
                enabled=True,
                country_code=port_info["country"]
            ),
        ) as stream:
            for event in stream:
                if event.type == EventType.COMPLETE:
                    congestion_data[port_info["port"]] = event.result_json
    
    return congestion_data

# Track congestion and alert if above threshold
congestion = track_port_congestion()
for port, data in congestion.items():
    if data.get("wait_time_hours", 0) > 48:
        print(f"⚠️  ALERT: {port} congestion high - {data['wait_time_hours']}h wait")
```

### Key Patterns

- **Geographic proxies**: Route through each port's region for accurate data
- **Real-time updates**: Schedule runs every 6-12 hours
- **Alert thresholds**: Trigger notifications when wait times spike
- **Historical tracking**: Store data to identify patterns
- **Predictive alerts**: Use trends to forecast future congestion

---

## Best Practices from the Cookbook

### 1. Always Use Appropriate Profiles

```python
# Public sites without bot detection
browser_profile=BrowserProfile.LITE

# Retail, financial, government sites
browser_profile=BrowserProfile.STEALTH
```

### 2. Geographic Proxies for Regional Data

```python
# Shopping price comparison in US
proxy=ProxyConfig(enabled=True, country_code=ProxyCountryCode.US)

# EU regulatory data
proxy=ProxyConfig(enabled=True, country_code=ProxyCountryCode.DE)
```

### 3. Parallel Execution for Multiple Sites

```python
# Don't loop sequentially
for site in sites:
    run_agent(site)  # ❌ Slow

# Instead use concurrent patterns
tasks = [run_agent_async(site) for site in sites]
await asyncio.gather(*tasks)  # ✅ Fast
```

### 4. Rate Limiting and Respect

```python
# Between requests to same site
time.sleep(2)

# Between different sites
time.sleep(1)

# Random jitter to appear human
import random
time.sleep(random.uniform(1, 3))
```

### 5. Error Handling and Retries

```python
max_retries = 3
for attempt in range(max_retries):
    try:
        with client.agent.stream(...) as stream:
            # process
    except Exception as e:
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # Exponential backoff
        else:
            raise
```

---

## Related Resources

- [TinyFish Cookbook on GitHub](https://github.com/tinyfish-io/tinyfish-cookbook)
- [Quick Start](./10-quickstart-python.md)
- [Web Scraping Examples](./20-scraping-examples.md)
- [Stealth Mode and Proxies](./40-stealth-and-proxies.md)
- [API Reference](./50-api-reference.md)
