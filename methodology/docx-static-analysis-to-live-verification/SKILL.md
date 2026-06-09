---
name: docx-static-analysis-to-live-verification
description: When given static analysis docx reports, verify each claim against live code before applying fixes. Avoids wasting time on false positives from document-only analysis.
---

# Static Analysis Docx → Live Code Verification Workflow

## When to Use
When given a large docx file containing code review findings or optimization suggestions, systematically verify each item against live code/runtime rather than blindly applying every recommendation.

## Why
Static analysis docx reports (e.g., from GitHub repository scans) contain many false positives:
- "Prefix double stacking" turns out to be correct behavior when inner routers already have full prefixes
- "Module X missing" when it never existed (`services/monitoring`)
- Assumptions about database credentials that require runtime inspection to confirm
- OpenAPI schema paths can differ from actual registered routes

## Workflow

### 1. Read all docx files first
Extract text from all .docx files, build a master issue list with file/line references.

### 2. Create TODO list
One item per issue with ID (e.g., `01-1`, `02-3`) referencing the source docx.

### 3. For each item, verify live before touching code
```bash
# API endpoints — always verify with curl first
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin@123456"}' | \
  python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

curl -s "http://localhost:8000/<actual-path>" -H "Authorization: Bearer $TOKEN"
```

### 4. Common false positive patterns
- **Prefix stacking**: Check if inner router already has full prefix before claiming main.py override is wrong
- **Missing files/modules**: Search filesystem first (`find . -name "*.py" | grep keyword`)
- **OpenAPI vs reality**: OpenAPI schema may not reflect mounted prefixes; always curl the actual endpoint
- **Database access**: `.env` files may echo `***` in terminal; use `pymysql.connect` in execute_code to test credentials rather than guessing

### 5. Fix only confirmed issues
If an item verifies as already correct or the "problem" is a design choice, mark complete and move on.

### 6. Group related fixes
Multiple small fixes in the same file can be committed together with one descriptive commit message.

### 7. Restart API after backend changes
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Key Lessons from itops-platform verification
- `device_api.py` self-declares `prefix="/api/v1/devices"`, main.py adds `prefix=""` → correct, no stacking
- `sharding_router` had `prefix="/sharding"` internally, registered with `prefix="/api/v1"` in main → correct path `/api/v1/sharding/...`
- `create_task()` without capturing return value = task handle lost, shutdown cancel fails
- SPA fallback POST/PUT/DELETE returning index.html is wrong — only GET should fallback

## Git Workflow for These Fixes
```bash
git add -A && git diff --cached --stat
git commit -m "fix: <category> - <what changed>"
git push github main
```
