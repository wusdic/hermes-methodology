---
name: document-to-codebase-sync-verification
description: Verify documents match actual codebase before executing plans — prevents wasting time on outdated assumptions
---

# Document-to-Codebase Sync Verification

## When to Use
When given a task/plan/todo based on a document, **always verify the document matches the actual codebase before executing**. Assumptions about file paths, function names, or architecture that worked months ago may be completely wrong after refactoring.

## The Pattern
1. Document says: `api/routes/asset.py` exists and has X endpoints
2. Actual code has: `app/domains/asset/router.py` (new architecture) OR no such file at all
3. **The document and codebase are out of sync**

## How to Verify Quickly
```bash
# 1. Check if key files from the doc actually exist
ls api/routes/asset.py  # Old path
ls app/domains/asset/router.py  # New path

# 2. API smoke test (fastest way to verify what's actually running)
curl -s http://localhost:8000/api/v1/assets/ | head -c 200

# 3. Check git history for recent refactoring
git log --oneline -10 --name-only | head -40

# 4. Count actual registered routes
curl -s http://localhost:8000/openapi.json | python3 -c "
import sys,json
d=json.load(sys.stdin)
paths = list(d.get('paths',{}).keys())
print(f'Total routes: {len(paths)}')
print('\n'.join(sorted(paths)[:20]))
"
```

## Key Signals You're Out of Sync
- Task list references files that don't exist
- Task list assumes API paths that return 404
- Document mentions a module/function/class that grep can't find
- Codebase has directory structure completely different from what doc describes

## Action Plan When Out of Sync
1. **Stop** executing the old plan
2. **Verify** actual state with API testing (curl)
3. **Update** the document to reflect reality
4. **Get user alignment** on new priorities before continuing
5. **Commit** document updates before proceeding with code changes

## Example from ITOps Platform (2026-05-29)
- TODO.md said Phase 1-3 "✅ 核心完成", Phase 10 "未开始"
- Task list assumed `api/routes/asset.py` existed (old architecture)
- Actual code: `app/domains/asset/router.py` (new 13-domain architecture)
- Action: Pivoted to comprehensive API testing, found 19/20 working
- Updated TODO.md to mark Phase 4-9 as complete, Phase 10 as not started
- Committed doc changes before proceeding

## Why This Matters
Following an outdated plan wastes time fixing things that aren't broken, and misses things that are actually broken. The document is the contract with the user — it must match reality.
