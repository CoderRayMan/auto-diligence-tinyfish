# TinyFish Web Agent – Stealth Mode and Proxies

## Understanding Bot Protection

Many sites have anti-bot measures that block automated requests:

- **Browser fingerprinting**: Detecting headless browsers or automation tools
- **Rate limiting**: Blocking too many requests from a single IP
- **Behavioral analysis**: Flagging inhuman mouse movement, typing speed, or navigation patterns
- **Geographic restrictions**: Blocking requests from certain countries or IP ranges

TinyFish's stealth mode and proxy support help overcome these challenges.

## Browser Profiles

TinyFish supports two browser profiles:

### LITE Profile (Default)

Standard browser behavior. Good for most public sites without bot protection.

```python
from tinyfish import TinyFish, BrowserProfile

client = TinyFish()

with client.agent.stream(
    url="https://example.com",
    goal="Extract product information",
    browser_profile=BrowserProfile.LITE,
) as stream:
    for event in stream:
        print(event)
```

### STEALTH Profile

Advanced anti-detection browser. Mimics human behavior and evades bot detection.

```python
from tinyfish import TinyFish, BrowserProfile

client = TinyFish()

with client.agent.stream(
    url="https://protected-site.com",
    goal="Extract product information",
    browser_profile=BrowserProfile.STEALTH,
) as stream:
    for event in stream:
        print(event)
```

**What STEALTH mode does:**

- Hides automation markers in the browser
- Randomizes mouse movements and typing speed
- Mimics natural user behavior patterns
- Handles anti-automation JavaScript challenges
- Maintains consistent browser fingerprinting
- Handles complex CAPTCHA and verification flows (where applicable)

## Proxy Configuration

Route requests through specific geographic locations using proxies.

### Basic Proxy Usage

```python
from tinyfish import TinyFish, ProxyConfig, ProxyCountryCode

client = TinyFish()

with client.agent.stream(
    url="https://geo-restricted-site.com",
    goal="Extract data",
    proxy_config=ProxyConfig(
        enabled=True,
        country_code=ProxyCountryCode.US,
    ),
) as stream:
    for event in stream:
        print(event)
```

### Supported Country Codes

Common proxy country codes:

```python
from tinyfish import ProxyCountryCode

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
```

For a complete list, check the TinyFish API documentation.

### Disable Proxy

```python
with client.agent.stream(
    url="https://example.com",
    goal="Extract data",
    proxy_config=ProxyConfig(enabled=False),
) as stream:
    for event in stream:
        print(event)
```

## Combining Stealth Mode and Proxies

Use stealth mode and proxies together for maximum bot evasion:

```python
from tinyfish import TinyFish, BrowserProfile, ProxyConfig, ProxyCountryCode

client = TinyFish()

with client.agent.stream(
    url="https://highly-protected-site.com",
    goal="Extract sensitive data",
    browser_profile=BrowserProfile.STEALTH,
    proxy_config=ProxyConfig(
        enabled=True,
        country_code=ProxyCountryCode.US,
    ),
) as stream:
    for event in stream:
        print(event)
```

## Use Cases for Stealth + Proxies

### 1. Government and Regulatory Sites

Many government portals have aggressive bot protection.

```python
with client.agent.stream(
    url="https://osha.gov/enforcement-records",
    goal="Extract enforcement action records for company XYZ",
    browser_profile=BrowserProfile.STEALTH,
    proxy_config=ProxyConfig(enabled=True, country_code=ProxyCountryCode.US),
) as stream:
    for event in stream:
        print(event)
```

### 2. Competitor Price Monitoring

Avoid detection while monitoring competitor pricing:

```python
with client.agent.stream(
    url="https://competitor.com/products",
    goal="Extract current product prices",
    browser_profile=BrowserProfile.STEALTH,
    proxy_config=ProxyConfig(enabled=True, country_code=ProxyCountryCode.CA),
) as stream:
    for event in stream:
        print(event)
```

### 3. Geo-Restricted Content

Access region-specific content:

```python
with client.agent.stream(
    url="https://regional-site.com/news",
    goal="Extract news from the regional site",
    browser_profile=BrowserProfile.STEALTH,
    proxy_config=ProxyConfig(enabled=True, country_code=ProxyCountryCode.UK),
) as stream:
    for event in stream:
        print(event)
```

### 4. Multi-Region Testing

Test the same site from different geographic regions:

```python
regions = [
    ProxyCountryCode.US,
    ProxyCountryCode.UK,
    ProxyCountryCode.DE,
    ProxyCountryCode.JP,
]

for country in regions:
    with client.agent.stream(
        url="https://example.com",
        goal="Extract site content",
        browser_profile=BrowserProfile.STEALTH,
        proxy_config=ProxyConfig(enabled=True, country_code=country),
    ) as stream:
        for event in stream:
            print(f"Region {country.name}:", event)
```

## Rate Limiting and Throttling

Even with stealth mode and proxies, respect site rate limits:

### Conservative Approach

```python
import time
from tinyfish import TinyFish, BrowserProfile, ProxyConfig, ProxyCountryCode

client = TinyFish()

urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3",
]

for url in urls:
    with client.agent.stream(
        url=url,
        goal="Extract data",
        browser_profile=BrowserProfile.STEALTH,
        proxy_config=ProxyConfig(enabled=True, country_code=ProxyCountryCode.US),
    ) as stream:
        for event in stream:
            print(event)
    
    # Wait between requests to avoid rate limiting
    time.sleep(3)  # 3 seconds between requests
```

### Randomized Throttling

Add randomization to avoid pattern detection:

```python
import time
import random
from tinyfish import TinyFish, BrowserProfile, ProxyConfig, ProxyCountryCode

client = TinyFish()

urls = ["https://example.com/page1", "https://example.com/page2"]

for url in urls:
    with client.agent.stream(
        url=url,
        goal="Extract data",
        browser_profile=BrowserProfile.STEALTH,
        proxy_config=ProxyConfig(enabled=True, country_code=ProxyCountryCode.US),
    ) as stream:
        for event in stream:
            print(event)
    
    # Random wait between 2-5 seconds
    wait_time = random.uniform(2, 5)
    print(f"Waiting {wait_time:.1f} seconds...")
    time.sleep(wait_time)
```

## Best Practices

### 1. Start Without Stealth

Test with `LITE` profile first. Only use `STEALTH` if needed:

```python
# Try LITE first
with client.agent.stream(
    url="https://example.com",
    goal="Extract data",
    browser_profile=BrowserProfile.LITE,
) as stream:
    for event in stream:
        print(event)

# If you get blocked, switch to STEALTH
```

### 2. Monitor Response Times

Stealth mode adds overhead. Monitor performance:

```python
import time

start = time.time()

with client.agent.stream(
    url="https://example.com",
    goal="Extract data",
    browser_profile=BrowserProfile.STEALTH,
) as stream:
    for event in stream:
        print(event)

elapsed = time.time() - start
print(f"Execution time: {elapsed:.2f} seconds")
```

### 3. Use Appropriate Country Codes

Match the proxy country to the site's geographic focus:

```python
# For US government sites, use US proxy
with client.agent.stream(
    url="https://sec.gov/cgi-bin/browse-edgar",
    goal="Extract filing data",
    proxy_config=ProxyConfig(enabled=True, country_code=ProxyCountryCode.US),
) as stream:
    for event in stream:
        print(event)

# For EU sites, use EU proxy
with client.agent.stream(
    url="https://europa.eu/data",
    goal="Extract data",
    proxy_config=ProxyConfig(enabled=True, country_code=ProxyCountryCode.DE),
) as stream:
    for event in stream:
        print(event)
```

### 4. Handle Rate Limiting Gracefully

Implement retry logic with exponential backoff:

```python
import time
from tinyfish import TinyFish, BrowserProfile, ProxyConfig, ProxyCountryCode

def run_with_retry(url, goal, max_retries=3):
    client = TinyFish()
    
    for attempt in range(max_retries):
        try:
            with client.agent.stream(
                url=url,
                goal=goal,
                browser_profile=BrowserProfile.STEALTH,
                proxy_config=ProxyConfig(enabled=True, country_code=ProxyCountryCode.US),
                timeout_seconds=30,
            ) as stream:
                for event in stream:
                    print(event)
                return  # Success
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"Attempt {attempt + 1} failed. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"All {max_retries} attempts failed")
                raise
```

### 5. Log Configuration for Debugging

Track which settings you're using:

```python
def run_with_logging(url, goal, use_stealth=True, country_code=ProxyCountryCode.US):
    print(f"URL: {url}")
    print(f"Goal: {goal}")
    print(f"Stealth: {use_stealth}")
    print(f"Proxy Country: {country_code.name}")
    
    client = TinyFish()
    
    with client.agent.stream(
        url=url,
        goal=goal,
        browser_profile=BrowserProfile.STEALTH if use_stealth else BrowserProfile.LITE,
        proxy_config=ProxyConfig(enabled=True, country_code=country_code),
    ) as stream:
        for event in stream:
            print(event)
```

## Troubleshooting

### "Blocked or Rate Limited"

- Increase wait time between requests
- Switch to STEALTH profile
- Use a different proxy country
- Check if the site requires JavaScript rendering (use TinyFish's default behavior)

### "Timeout"

- Increase the `timeout_seconds` parameter
- Use STEALTH profile (some sites require it for proper detection)
- Check network connectivity

### "Proxy Error"

- Verify the proxy country code is valid
- Check if proxies are enabled in your account
- Try disabling proxy and retrying

## Related

- [Quick Start](./10-quickstart-python.md) – Get started with TinyFish
- [Web Scraping Examples](./20-scraping-examples.md) – Learn scraping patterns
- [Forms and Authentication](./30-forms-and-auth.md) – Handle login flows
