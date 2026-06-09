---
name: naive-ui-pagination-debugging
description: n-data-table remote 分页只显示第1页——Naive UI Object.assign 破坏响应式追踪，getPaginationConfig() 纯对象函数是唯一可靠解法
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [vue, naive-ui, frontend, pagination, reactivity]
    related_skills: [naive-ui-pagination-remote-workaround, naive-ui-debugging]
---

# Naive UI Pagination Debugging

## Problem
`n-data-table` with `remote=true` shows only page 1 — page 2 button never appears even when `total` > `pageSize`. Browser DOM shows `total=28, page=1, buttonCount=3` (prev/1/next only).

## Root Cause
Naive UI `n-data-table` uses `Object.assign({}, props.pagination)` internally. This causes **total to become the string `"undefined"`** (not a number), resulting in only page 1 being shown with no page 2 button. Three patterns fail:
1. `reactive({...})` — loses reactivity through Object.assign
2. `ref({...})` — Vue auto-unwraps in templates but Object.assign still gets plain object without reactive tracking
3. `computed(() => ({...}))` — creates new object reference on each access, Naive UI loses internal pagination state

**Verified via browser console**: `JSON.stringify({total, activePage, buttonCount})` returned `{"total":"28","activePage":"1","buttonCount":3}` — total is STRING "28", meaning the reactive tracking was lost.

## Working Solution: Plain Object with Individual Refs + Manual Sync

Use `page`, `pageSize`, `total` as individual `ref()` values. `paginationConfig` is a **plain JS object** (not reactive). Manual sync in both directions:

```javascript
// Define individual refs
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// Plain object — Naive UI's Object.assign gets a plain object, works correctly
const paginationConfig = {
  page: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (p) => {
    page.value = p
    paginationConfig.page = p
    loadData() // fetch new page
  },
  onUpdatePageSize: (size, p) => {
    pageSize.value = size
    paginationConfig.pageSize = size
    page.value = 1
    paginationConfig.page = 1
    loadData()
  }
}

// In loadData():
const data = await fetch(...) 
total.value = data.total
paginationConfig.total = data.total  // MUST sync both ways

// Template:
<n-data-table :pagination="paginationConfig" ...>
```

Key insight: Give Naive UI a plain JS object whose properties are updated from refs. Object.assign works fine on plain objects. We manually keep the plain object and refs in sync.

- `reactive()`: `Object.assign` creates a new plain object, severing the reactive proxy chain
- `ref()`: Vue auto-unwraps in templates, but Naive UI receives a plain object through `Object.assign` that its internal `watch()` cannot track

The `mergedItemCountRef` computed inside Naive UI returns `undefined` because it can't access `props.pagination.itemCount` through the assigned object.

## Confirmed Working Solution: watchEffect + Plain Shared Object (v1.3)

The **manual sync after each load** approach above is fragile (easy to forget syncing in all code paths). The reliable approach uses `watchEffect` to auto-sync whenever any ref changes:

```js
import { ref, watchEffect } from 'vue'

const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// Stable plain JS object — Naive UI's Object.assign copies from this
const paginationConfig = {
  page: 1, pageSize: 20, total: 0,
  showSizePicker: true, pageSizes: [10, 20, 50, 100],
  onChange: (p) => {
    page.value = p
    loadData()
  },
  onUpdatePageSize: (s) => {
    pageSize.value = s
    page.value = 1
    loadData()
  }
}

// watchEffect 主动同步：total/page/pageSize 变化时 Naive UI 收到最新值
watchEffect(() => {
  paginationConfig.page = page.value
  paginationConfig.pageSize = pageSize.value
  paginationConfig.total = total.value
  paginationConfig.itemCount = total.value  // Naive UI reads itemCount, NOT total
  paginationConfig.pageCount = Math.max(1, Math.ceil((total.value || 0) / (pageSize.value || 1)))
})

async function loadData() {
  const res = await fetch(`/api/list?page=${page.value}&page_size=${pageSize.value}`)
  const data = await res.json()
  items.value = data.items || []
  total.value = data.total || 0
  // With watchEffect: NO manual sync needed — watchEffect re-runs when total.value changes
  // With manual sync (v1.2): must sync all three every time total.value changes
}
```

Template: `<n-data-table :pagination="paginationConfig" :remote="true">`

**Why watchEffect is better**: any code path that changes `page.value`, `pageSize.value`, or `total.value` automatically syncs to `paginationConfig`. No need to remember manual sync after every `loadData()` call or `onChange`/`onUpdatePageSize`.

### CRITICAL: Template Binding — Direct Object, NOT Function Call

The template binding syntax is as important as the data structure:

```html
<!-- ✅ CORRECT: direct binding — Naive UI receives paginationConfig reference -->
<n-data-table :pagination="paginationConfig" :key="paginationVersion" ...>

<!-- ❌ WRONG: function call — called on every render, Object.assign gets
    a fresh return value each time; Naive UI cannot maintain stable internal state,
    mergedItemCountRef returns undefined, only page 1 shown -->
<n-data-table :pagination="getPaginationConfig()" ...>
```

**Why `:pagination="getPaginationConfig()"` fails**: Every time the Vue component re-renders, the template expression `getPaginationConfig()` is evaluated, returning a **new object reference**. Naive UI's `Object.assign({}, props.pagination)` then copies from this new object. Because the object is freshly returned each render, Naive UI's internal `watch` on pagination props fires with stale/partial data, and `mergedItemCountRef` ends up `undefined`.

**Why `:pagination="paginationConfig"` works**: The component holds one stable `paginationConfig` object. `watchEffect` keeps its properties in sync with the refs. Naive UI receives the same object reference on every render. `Object.assign` works on the same object, Naive UI's internal state remains stable.

**The `:key` attribute**: Use `:key="paginationVersion"` (a `ref(0)` incremented with `paginationVersion.value++` whenever you want to force Naive UI to re-render the table, e.g., after loading new data). This ensures Naive UI re-reads the full pagination config.

## Alternative: Plain Object + Manual Sync (v1.2, less robust)

```js
import { ref } from 'vue'
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const paginationConfig = {
  page: 1, pageSize: 20, itemCount: 0,
  showSizePicker: true, pageSizes: [10, 20, 50, 100],
  onChange: (p) => {
    page.value = p
    paginationConfig.page = p
    loadData()
  },
  onUpdatePageSize: (s) => {
    pageSize.value = s
    page.value = 1
    paginationConfig.pageSize = s
    paginationConfig.page = 1
    loadData()
  }
}

async function loadData() {
  const res = await fetch(`/api/list?page=${page.value}&page_size=${pageSize.value}`)
  const data = await res.json()
  items.value = data.items || []
  total.value = data.total || 0
  // Manual sync required after every loadData()
  paginationConfig.itemCount = total.value
  paginationConfig.total = total.value
}
```

## Critical: itemCount + pageCount
Naive UI uses `itemCount` and `pageCount` (not just `total`) to compute `buttonCount`. Always sync all three:
```js
paginationConfig.total = total.value
paginationConfig.itemCount = total.value
paginationConfig.pageCount = Math.max(1, Math.ceil((total.value || 0) / (pageSize.value || 1)))
```

## Browser Verified: 2026-05-22

**Confirmed working in production on ITOps Platform** (devices.vue + alerts.vue with Naive UI 2.43.2).

The `watchEffect + plain paginationConfig object` approach is **correct and verified**. When browser shows `total=0` with only page 1 buttons, that is expected behavior (empty database), NOT a code bug.

**Verified in browser**:
```javascript
// Device page — pagination div attributes:
<div class="n-pagination" total="0">  // total=0 → only prev/1/next buttons is CORRECT
// Alert page — "告警列表 共 0 条" is correct display
```

**If pagination still broken after implementing solution, check**:
1. Browser console: `document.querySelector('.n-pagination')?.getAttribute('total')` — if `total="0"` → database is empty, not a code issue
2. Network tab: verify API returns `{"items": [...], "total": 28, ...}` with the correct non-zero total
3. `watchEffect` must be inside setup (not outside the component), and must reference `total.value` to establish reactive dependency

## ⚠️ API 422 + Loading Spinner = Silent Failure (Critical Debug Pattern)

**Symptoms**: Table shows loading spinner forever, then "暂无数据" or empty table. No obvious error in browser console.

**Root cause pattern**: Backend rejects `page_size=N` with HTTP 422 (validation error — e.g., N exceeds backend `Query(..., le=200)` constraint). Axios interceptor catches the error and the component's `catch` block shows a brief error message that gets immediately hidden by the table's loading spinner. Visually appears as "blank" or "no data".

**Verification**: Check backend server logs, NOT browser console. Server logs show:
```
GET /api/v1/assets/device?page=1&page_size=500 → 422 Unprocessable Content
```

**Step-by-step diagnosis**:
1. `process(action='log', limit=N)` on the backend server session — look for 422 on the endpoint
2. `curl` the endpoint with the same params to see the actual error
3. Check `dependencies.py` for `Query(..., le=N)` constraints — frontend may pass a value exceeding N
4. Check the component's `catch` block — it may be hiding the real error behind a loading state

**Real case (ITOps Platform 2026-05-28)**:
- Frontend `devices.vue` called `devices.getList({ page: 1, page_size: 500 })`
- Backend `PaginationParams` had `le=100` → 422
- Server log: `GET /api/v1/assets/device?page=1&page_size=500 → 422`
- Component `catch` showed brief "加载监控设备失败" but spinner hid it immediately
- Fix: reduce `page_size` to a value within backend's limit (200)

## ⚠️ Important: "Only Page 1" Is Sometimes CORRECT Behavior

**Do NOT assume a pagination bug if only page 1 shows.** If the API returns `total=1` (or any value ≤ `pageSize`), only page 1 is correct and expected — there genuinely is no page 2.

**How to verify in browser**:
```javascript
document.querySelector('.n-pagination')?.getAttribute('total')  // → "1" (string)
document.querySelector('.n-pagination').textContent  // → "20 / 页" (page size) + "1" (current page)
// Check API response directly in Network tab
// API should return {"items": [...], "total": N} where N > pageSize for page 2 to appear
```

**Always curl the API first before assuming a frontend bug**:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin@123456"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# Verify total from API — if total ≤ 20, only page 1 is correct
curl "http://localhost:8000/api/v1/assets/device?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN" | python3 -c \
  'import sys,json; d=json.load(sys.stdin); print("total=" + str(d["total"]) + ", items=" + str(len(d["items"])))'
```

If API returns `total > pageSize` (e.g., `total=28, page_size=20`) but UI still shows only page 1 → **this IS the Naive UI bug**, apply the `watchEffect + paginationConfig` solution above.

## ⚠️ Vite Build: index.html May Reference Stale Chunk Hash

After `npm run build`, `index.html` references a specific hash like `index-Cj_I4f-4.js`. If you previously modified `vite.config.js` `outDir` (e.g., changed from `dist` to `dist-new` to fix EACCES permission errors), the newly built chunk may have a **different hash** (e.g., `index-DfyD2RhD.js`) that `index.html` doesn't reference.

**Symptoms**: Code changes (pagination fix, new functions) don't appear in browser even after `npm run build` succeeds. Browser loads the OLD chunk.

**How to diagnose**:
```bash
# Check what chunk the built index.html references
grep "script" dist/index.html
# → <script type="module" crossorigin src="/assets/index-Cj_I4f-4.js"></script>

# Check what chunks were actually built
ls -la dist/assets/index-*.js
# → index-Cj_I4f-4.js  (old)
# → index-DfyD2RhD.js  (NEWLY BUILT, but not referenced!)

# Verify new chunk contains your code
grep "yourNewFunction" dist/assets/index-DfyD2RhD.js  # should match
grep "yourNewFunction" dist/assets/index-Cj_I4f-4.js  # should NOT match
```

**Fix**: Manually patch `dist/index.html` to reference the new chunk:
```bash
# Replace old hash with new hash in index.html
sed -i 's/index-Cj_I4f-4/index-DfyD2RhD/g' dist/index.html
```

**Prevention**: After any `npm run build`, always verify `index.html` script src matches the actual built chunk. Or use a consistent `outDir` that doesn't create hash mismatches.

## Confirmed Invalid Approaches (tried and failed in production)
- ❌ `const pagination = reactive({...})` — `Object.assign` severs reactive proxy chain, mergedItemCountRef returns undefined
- ❌ `const pagination = ref({...})` — Vue auto-unwraps in template, but Object.assign inside Naive UI still gets non-reactive object; mergedItemCountRef still broken
- ❌ `const paginationConfig = computed(() => ({...}))` — returns new object reference on each access, resets Naive UI internal pagination state; page jumps back to 1 on every render
- ❌ `const pagination = ref({...})` + template `:pagination="pagination"` — same issue as above; auto-unwrapping doesn't help Naive UI's Object.assign
- ❌ `const pagination = reactive({...})` + template `:pagination="pagination"` — Naive UI Object.assign creates plain copy, reactive tracking lost
- ❌ `:pagination="getPaginationConfig()"` — function call on every render returns a new object; Naive UI's Object.assign creates from a fresh return value each time; internal pagination state resets; mergedItemCountRef → undefined; only page 1 shown
- ❌ `:pagination="getPaginationConfig()"` — even with stable `paginationConfig` object inside the function, Naive UI's internal watcher sees a different prop value on each render, resetting pagination state
- ❌ Passing a plain object without syncing `itemCount` after `loadData()` — Naive UI sees stale total, buttonCount still wrong
- ❌ `paginationConfig.page = 1` on a returned function object without re-calling the function — ReferenceError (plain object, not a ref)
- ❌ Template function call + `:key` on the table — `:key` forces re-render but Naive UI still sees a new function return value on each render, compounding the problem

## Known Bug: ReferenceError from Confusing Return Value with Ref
A common mistake: `getPaginationConfig()` returns a **plain object** (not a `ref` or `reactive`). Code that tries to do `paginationConfig.page = 1` later (without re-calling the function) gets a `ReferenceError` because `paginationConfig` is a plain variable, not a Vue ref.

**Correct approach**: Always re-call `getPaginationConfig()` or explicitly update the individual `ref()` values:
```js
// ✅ Correct: update the ref, then re-render triggers getPaginationConfig() → fresh object
page.value = 1
loadData()

// ❌ Wrong: ReferenceError — paginationConfig is a plain object returned by getPaginationConfig(), not a ref
paginationConfig.page = 1

// ❌ Wrong: paginationConfig is not reactive, changes won't trigger Naive UI re-render
const paginationConfig = reactive(getPaginationConfig())
paginationConfig.page = 1  // won't propagate to Naive UI
```

## Multiple Tables
Each `n-data-table` on the same page needs its own separate set of refs and its own `paginationConfig` object. Do not share pagination state between two tables.

## Known Bug: ReferenceError from Confusing Return Value with Ref
