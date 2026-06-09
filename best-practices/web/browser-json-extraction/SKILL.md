---
name: browser-json-extraction
description: Extract JSON data from a webpage's body text when browser_navigate/page loading times out, using browser_console JavaScript execution
---
# Browser JSON Extraction Workaround

## Problem
When a webpage's JSON API endpoint (`/json`) loads successfully but the page itself times out or becomes unparseable, you cannot navigate to it or use `browser_snapshot` to read the content.

## Solution
Use `browser_console` to execute JavaScript that parses `document.body.innerText` as JSON:

```javascript
JSON.parse(document.body.innerText)
```

Then extract fields directly:
```javascript
JSON.parse(document.body.innerText).info.version
JSON.parse(document.body.innerText).releases["0.15.2"][0].upload_time
```

## Verified Working Cases
- PyPI `/pypi/{package}/json` endpoint — returns JSON in page body
- Any REST API that embeds JSON in page body (not just XHR/fetch responses)

## Why This Works
The raw JSON is in `innerText` even when:
- Page navigation times out
- Page renders unparseable HTML
- CDN/resources fail to load

## Limitation
Browser console evaluates JavaScript in the page's DOM context. If the page redirected or the JSON was loaded via XHR (not in initial HTML), `innerText` won't contain it.

## When to Use
- `browser_navigate` succeeds but page is blank/times out
- `browser_snapshot` returns truncated/unusable content
- You need structured data (versions, prices, IDs) from a page that has a JSON API
