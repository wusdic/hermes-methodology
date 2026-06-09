---
name: api-gap-analysis
description: Systematically verify frontend API calls against backend FastAPI routes — find path/method mismatches, missing routes, and prefix misconfigurations
tags: [fastapi, vue, api, debugging]
---

# API Gap Analysis — Frontend vs Backend

## When to Use
When you need to systematically verify that a frontend (Vue/React) actually calls backend APIs that exist and match in path, method, and response format. This is NOT a one-shot grep — it's a structured discovery process.

## Prerequisites
- Project path known
- Backend: FastAPI routes in `api/routes/`
- Frontend: Vue views in `frontend/src/views/` + API files in `frontend/src/api/`
- Backend router registered in `api/main.py` with `include_router(..., prefix="...")`

## Step 1 — Inventory Both Sides (parallel)

### Backend: Get all routes with prefixes
```bash
grep -n "@router\.\(get\|post\|put\|delete\|patch\)" api/routes/*.py
grep -n "include_router" api/main.py
```

Read `api/main.py` lines ~255-410 to get the actual prefix for each router module (the `prefix=` argument in `include_router`). CRITICAL: routers defined with `APIRouter(prefix="")` get their prefix entirely from `include_router`.

### Frontend: Get all API calls
```bash
grep -rn "get\|post\|put\|delete\|patch\|request\." frontend/src/api/
grep -l "import.*from.*api" frontend/src/views/**/*.vue
```

## Step 2 — Build a Mapping Table

For each frontend API file, record:
```
module | method | frontend_path | backend_prefix | expected_full_path
```

For backend, you need TWO things for each router:
1. The `prefix` from `include_router` in main.py
2. The `prefix` (if any) from `router = APIRouter(prefix="...")` in the route file itself

**Full path = include_router_prefix + router_file_prefix + route_path**

## Step 3 — Critical Prefix Traps

### Trap 1: include_router overrides file-level prefix
```python
# automation.py
router = APIRouter()  # NO file-level prefix

# main.py
app.include_router(automation_router, prefix="/api/v1/automation")
# → Full path = /api/v1/automation + "" + /scripts
# → /api/v1/automation/scripts
```

### Trap 2: Some routers have NO include_router prefix
Routes registered with `prefix=""` use only their file-level prefix.
```python
# device_api.py
router = APIRouter(tags=["设备管理"], prefix="/api/v1/devices")

# main.py
app.include_router(device_router, prefix="")
# → Full path = "" + /api/v1/devices + /devices
# VERIFY with: curl http://localhost:8000/openapi.json | grep devices
```

### Trap 3: Method mismatch (PUT vs POST)
Common in alert acknowledge/resolve — frontend says `PUT /alerts/{id}/acknowledge` but backend has `POST /alerts/{id}/acknowledge`.

## Step 4 — Systematic Verification Commands

```bash
# Login and get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin@123456"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin).get("data",{}).get("access_token",""))')

# Verify endpoint exists with correct method
curl -s -X POST "http://localhost:8000/api/v1/discovery/ip/scan" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cidr":"10.0.0.0/30"}'
```

## Step 5 — Categorize Issues

| Type | Description | Fix |
|------|-------------|-----|
| **A** | Frontend calls path that doesn't exist at all | Add backend route OR remove frontend call |
| **B** | Method mismatch (PUT vs POST) | Change frontend method |
| **C** | Path structurally different words | Change frontend path to match backend |
| **D** | Route exists but under different prefix | Change frontend path |

Severity: 🔴 严重(崩溃) | 🟡 中等(数据缺失) | 🟢 微小(警告)

## Step 6 — Report Format

```
| 前端调用 | 后端实际 | 类型 | 后果 | 修复方式 |
```

## Critical: FastAPI Route Ordering — Shadowing Gotcha

**MOST IMPORTANT debugging pattern**: In FastAPI, route definition ORDER matters. A path like `/{id}` will shadow ALL fixed sub-paths defined AFTER it.

### Example (what goes wrong)
```python
@router.get("/{config_id}", summary="获取配置详情")       # ← Line 84: shadows everything below!
@router.get("/users-preview", summary="预览用户")         # ← NEVER MATCHED!
@router.get("/{config_id}/sync", summary="同步用户")     # ← NEVER MATCHED!
```

### Symptoms
- `GET /ldap/users-preview?server=test` returns `404 Not Found`
- `GET /alerts/stats` returns `404` or `422` (matched as `/{alert_id}` with alert_id="stats")
- `GET /assets/search?q=test` returns `404` (matched as `/{asset_id}` with asset_id="search")
- Any fixed sub-path that comes after a `/{param}` route is unreachable

### How to detect
```bash
# 1. Check OpenAPI spec — if a path is registered but returns 404, suspect shadowing
curl http://localhost:8000/openapi.json | python3 -c "
import sys,json
data = json.load(sys.stdin)
for p in data['paths']:
    if 'stats' in p or 'search' in p or 'preview' in p:
        print(p)
"

# 2. Check route definition order in the router file
grep -n '@router\.\|@app\.' api/routes/monitoring.py | head -20
# If /stats appears AFTER /{alert_id} → BUG

# 3. Test with integer path param — if it wrongly matches, path param shadows fixed routes
curl "http://localhost:8000/api/v1/monitoring/alerts/rule-stats" 
# → 422 "Input should be valid integer" = shadowing (path matched as /{alert_id})
```

### Fix
**Move all fixed paths BEFORE the first `/{param}` route**:
```python
# CORRECT order: fixed paths FIRST, then path params
@router.get("/users-preview", ...)    # ← fixed path first
@router.get("/{config_id}", ...)       # ← path param last
@router.get("/{config_id}/sync", ...) # ← sub-path of path param
```

### Files that needed this fix
- `api/routes/monitoring.py` — `/alerts/stats` was AFTER `/{alert_id}` (line ~678)
- `app/domains/asset/router.py` — `/search`, `/tags`, `/groups` were AFTER `/{asset_id}`
- `api/routes/ldap.py` — `/users-preview` was AFTER `/{config_id}`

## Common Issue Patterns (ITOps Platform specific)

**Confirmed and Fixed (2026-05):**
- `POST /api/v1/notifications/channels/{id}/test` — backend had `/test/{channel_id}`, fixed to match frontend
- `GET/POST/PUT/DELETE /api/v1/discovery/targets` — completely missing, added full CRUD + batch-delete + import/export
- `POST /api/v1/devices/import/{action}` — device_import_router had wrong prefix collision with device_api_router, remounted at `/api/v1/devices/import`
- `GET /api/v1/messages` — notification.js had 3 calls to `/notifications/history`, fixed to `/notifications/messages`

**Still Pending (2026-05):**
- P0-3: Device model chaos — `/assets/device` vs `/devices` two parallel interfaces sharing same table
- P0-5: Automation module — frontend scripts/tasks/executions vs backend trigger-rules mismatch
- P1-2: Notification unread-count (`/messages/unread-count`) not verified
- P1-4: Config snapshot `GET /assets/config/snapshot` returns 500
- P1-1: AI copilot/analyze pages are placeholder code (~30 lines)

## LDAP Mock Fallback Pattern

When implementing optional integrations (LDAP, SMTP, etc.) that have a mock/demo fallback:

```python
# WRONG: Only catches ImportError when ldap3 is not installed
try:
    import ldap3
    # real connection...
except ImportError:
    return mock_data

# BETTER: Catches both (1) ldap3 not installed AND (2) connection fails
try:
    import ldap3
    # real connection...
except Exception:
    # Connection failed OR ldap3 not installed → return mock data
    return mock_data
```

Root cause: `ldap3` is usually installed, so `ImportError` is never triggered. The actual connection failure raises `socket.gaierror`, `ldap3.core.exceptions.LDAPSocketOpenError`, etc. — all covered by `Exception`. Always use `except Exception` for graceful mock fallback.

## Critical Lesson: Static Analysis vs Runtime Verification

**Static code inspection alone is insufficient.** Many "issues" in requirement docs are false positives:

- A route can exist in code but return 500 at runtime (missing DB table, Redis dependency, import error)
- An "incorrect path" might actually work because FastAPI redirects (e.g., `/report/` → `/reports/`)
- "Hardcoded test data" in backend might be using real database joins (workorder.py zhangsan/lisi was a false alarm)
- Frontend API files may reference paths that don't exist — but code review won't catch which ones actually break

**Always use curl to verify, not just grep.** Trust actual HTTP responses over documentation or code inspection.

## False Positive Patterns (ITOps Platform specific)

These were listed as "issues" but verified NOT problems:
- `workorder.py` hardcoded zhangsan/lisi — all handlers use `JOIN user_table`, no hardcoded data
- `scheduler.js` incorrect paths — uses relative paths correctly, no hardcoded baseURL
- `notification.js` getHistory wrong path — actually calls correct `/messages` endpoint
- `report.js` `/report/` vs `/reports/` — FastAPI `report_singular_alias` handles redirect

## Systematic Verification Workflow (proven in production)

1. **Phase 1 — Fast inventory** (delegate_task parallel scan, 50+ files)
2. **Phase 2 — Classify issues** (confirmed bug vs needs-curl vs false-positive)
3. **Phase 3 — curl verify critical paths** (login → token → test each suspect endpoint)
4. **Phase 4 — Fix one at a time with git commit** (never batch fixes)

## Output Files
- `/tmp/backend_apis_full.md` — complete backend route inventory
- `/tmp/frontend_pages_full.md` — complete frontend page + API inventory
- `/tmp/gap_check_1.md` — detailed gap check results
