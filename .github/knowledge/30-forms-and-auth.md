# TinyFish Web Agent – Forms and Authentication

## Basic Form Submission

Fill and submit a simple form:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/contact",
    goal="""
    Fill out the contact form with:
    - Name: John Doe
    - Email: john@example.com
    - Message: I am interested in your services
    Then submit the form and confirm the submission was successful.
    Return the success message or confirmation page text.
    """,
) as stream:
    for event in stream:
        print(event)
```

## Login Workflow

Navigate a login flow with credentials:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/login",
    goal="""
    1. Enter the username: user@example.com
    2. Enter the password: securePassword123
    3. Click the Login button
    4. Verify you are logged in by checking for the user profile menu
    5. Return confirmation that login was successful
    """,
) as stream:
    for event in stream:
        print(event)
```

## Multi-Step Form Wizard

Navigate through a multi-page form:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/signup",
    goal="""
    Complete the 3-step registration form:
    
    Step 1 - Personal Information:
    - First Name: Jane
    - Last Name: Smith
    - Email: jane@example.com
    - Click Next
    
    Step 2 - Address:
    - Street: 123 Main St
    - City: New York
    - State: NY
    - ZIP: 10001
    - Click Next
    
    Step 3 - Review and Confirm:
    - Review all information
    - Check the Terms & Conditions checkbox
    - Click Submit
    
    Return the confirmation page content.
    """,
) as stream:
    for event in stream:
        print(event)
```

## Handling Dynamic Forms

Work with AJAX-loaded or dynamically appearing fields:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/search",
    goal="""
    1. Click the search input field
    2. Type "laptop" in the search box
    3. Wait for autocomplete suggestions to appear
    4. Click on the first suggestion
    5. Extract all results on the results page
    6. Return results as JSON with: name, price, rating
    """,
) as stream:
    for event in stream:
        print(event)
```

## Dropdown and Select Menus

Interact with dropdown selectors:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/filter",
    goal="""
    1. Click the "Category" dropdown
    2. Select "Electronics"
    3. Click the "Price Range" dropdown
    4. Select "$500 - $1000"
    5. Click the "Sort by" dropdown
    6. Select "Price: Low to High"
    7. Extract the filtered results
    8. Return all product listings as JSON
    """,
) as stream:
    for event in stream:
        print(event)
```

## Checkbox and Radio Button Selection

Select multiple or single options:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/preferences",
    goal="""
    In the preferences form:
    1. Check the "Email notifications" checkbox
    2. Check the "SMS alerts" checkbox
    3. Select "Daily" radio button for frequency
    4. Check the "Terms & Conditions" checkbox
    5. Click Save
    6. Verify settings were saved
    """,
) as stream:
    for event in stream:
        print(event)
```

## Authentication with 2FA/MFA

Handle two-factor authentication flows:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/login",
    goal="""
    1. Enter username: user@example.com
    2. Enter password: securePassword123
    3. Click Login
    4. A 2FA code prompt will appear
    5. Enter the 2FA code: 123456
    6. Click Verify
    7. Return confirmation that login was successful
    """,
) as stream:
    for event in stream:
        print(event)
```

## File Upload

Handle file input fields:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/upload",
    goal="""
    1. Click the file upload input
    2. Upload the file at /path/to/document.pdf
    3. Wait for upload to complete
    4. Verify the file appears in the upload list
    5. Click Submit
    6. Return the upload confirmation message
    """,
) as stream:
    for event in stream:
        print(event)
```

## Date and Time Input

Fill date and time picker fields:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/booking",
    goal="""
    1. Click the date input field
    2. Select date: March 25, 2026
    3. Click the time input field
    4. Select time: 2:30 PM
    5. Click the "Confirm Booking" button
    6. Return the booking confirmation details
    """,
) as stream:
    for event in stream:
        print(event)
```

## Session Persistence

Maintain login state across multiple requests:

```python
from tinyfish import TinyFish

client = TinyFish()

# First request: Login
with client.agent.stream(
    url="https://example.com/login",
    goal="Log in with username user@example.com and password pass123",
) as stream:
    for event in stream:
        print("Login:", event)

# Session is now active. Subsequent requests reuse the authenticated session.
# Access a protected page without needing to log in again.
with client.agent.stream(
    url="https://example.com/dashboard",
    goal="Extract the user dashboard summary and latest transactions",
) as stream:
    for event in stream:
        print("Dashboard data:", event)
```

## Handling Required Fields and Validation

Deal with form validation:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/form",
    goal="""
    1. Fill in the form with required fields:
       - Name: John Smith
       - Email: john@example.com
       - Phone: 555-123-4567
    2. Leave optional fields empty
    3. If validation errors appear, read and report them
    4. Correct any errors and resubmit
    5. Return success confirmation or error messages
    """,
) as stream:
    for event in stream:
        print(event)
```

## Testing Forms Programmatically

Extract form structure and test submission:

```python
from tinyfish import TinyFish

client = TinyFish()

with client.agent.stream(
    url="https://example.com/feedback",
    goal="""
    1. Analyze the feedback form structure
    2. Extract all field names and types
    3. Fill with appropriate test data
    4. Submit the form
    5. Return the form structure and submission result as JSON
    """,
) as stream:
    for event in stream:
        print(event)
```

## Best Practices

### 1. Use Clear Field Descriptions

```python
goal = """
Fill the contact form:
- In the "Full Name" field, enter: Jane Doe
- In the "Email Address" field, enter: jane@example.com
- In the "Subject" dropdown, select: General Inquiry
- In the "Message" text area, enter: Please contact me soon
"""
```

### 2. Handle Expected Errors

```python
with client.agent.stream(
    url="https://example.com/form",
    goal="Submit the form and handle any validation errors by correcting them",
) as stream:
    for event in stream:
        print(event)
```

### 3. Verify Successful Submission

Always confirm the form was submitted:

```python
goal = """
Fill and submit the form. After submission:
1. Wait for the success page to load
2. Extract the confirmation message or order number
3. Return the confirmation details
"""
```

### 4. Add Appropriate Waits

Let the agent handle waits for dynamic content:

```python
goal = """
Fill the search form and submit. After clicking submit:
1. Wait for the results page to load (may take a few seconds)
2. Extract all results
3. Return the results as JSON
"""
```

## Related

- [Quick Start](./10-quickstart-python.md) – Get started with TinyFish
- [Web Scraping Examples](./20-scraping-examples.md) – Extract data from pages
- [Stealth Mode and Proxies](./40-stealth-and-proxies.md) – Evade detection and route geographically
