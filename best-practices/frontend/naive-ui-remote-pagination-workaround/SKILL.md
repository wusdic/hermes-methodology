---
name: naive-ui-remote-pagination-workaround
description: Naive UI n-data-table remote pagination only shows page 1 — Object.assign loses reactive tracking, solved with plain object + individual refs + manual sync
triggers:
  - n-data-table remote pagination page 2 missing
  - Naive UI pagination mergedItemCountRef undefined
  - n-data-table showSizePicker not updating page count
---

# Naive UI n-data-table Remote Pagination Workaround

## Problem
`n-data-table` with `remote=true` only shows page 1 — no page 2 button. The `total` property is correctly returned by the API (e.g., 28 items, page 2 should exist), but the pagination UI shows only 3 buttons (prev/1/next) instead of "28条 1/2 页" with a page 2 button.

Console inspection reveals: `{total: "28", activePage: "1", buttonCount: 3}` — total is a **string** "28" (Naive UI string-coerces it) and `buttonCount: 3` means only 3 pagination buttons rendered.

## Root Cause
Naive UI internally does `Object.assign({}, props.pagination)` to copy the pagination props. This **loses Vue 3 reactivity** — whether you pass a `reactive()` object or a `ref()` object (auto-unwrapped in template), Naive UI's internal computed `mergedItemCountRef` cannot establish a reactive dependency on the `total` property through this plain object assign.

The computed thus returns `undefined` or stale value, causing incorrect pagination UI rendering.

## Solution: Plain Object + Individual refs

Use individual `ref()` for page/pageSize/total, and a **plain (non-reactive) object** `paginationConfig` that Naive UI receives. Manually sync both directions.

```js
// Individual refs
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// Plain object — NOT reactive(), NOT ref()
const paginationConfig = {
  page: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (p) => {
    page.value = p
    paginationConfig.page = p   // keep plain object in sync
    loadData()
  },
  onUpdatePageSize: (size) => {
    page.value = 1
    paginationConfig.page = 1   // keep plain object in sync
    pageSize.value = size
    paginationConfig.pageSize = size
    paginationConfig.total = total.value
    loadData()
  }
}
```

Template: `:pagination="paginationConfig"` (Vue auto-unwraps nothing since it's a plain object — Naive UI gets exactly what it expects)

In `loadData()`:
```js
const resp = await fetch(`/api/data?page=${page.value}&page_size=${pageSize.value}`)
const data = await resp.json()
items.value = data.items
total.value = data.total
paginationConfig.total = total.value   // critical: sync plain object after each load
```

In search/filter functions (reset to page 1):
```js
const handleSearch = () => {
  page.value = 1
  paginationConfig.page = 1           // must sync both
  loadData()
}
const handleClear = () => {
  page.value = 1
  paginationConfig.page = 1
  loadData()
}
```

In `onChange` (page number changed):
```js
onChange: (p) => {
  page.value = p
  paginationConfig.page = p           // keep plain object in sync
  loadData()
}
```

In `onUpdatePageSize` (page size changed — always reset to page 1):
```js
onUpdatePageSize: (size) => {
  page.value = 1
  paginationConfig.page = 1           // reset to first page
  pageSize.value = size
  paginationConfig.pageSize = size
  paginationConfig.total = total.value
  loadData()
}
```

## Template: Direct Object Binding, NOT Function Call

This is the most commonly missed detail:

```html
<!-- ✅ CORRECT: stable object reference -->
<n-data-table :pagination="paginationConfig" :key="paginationVersion" ...>

<!-- ❌ WRONG: function call — returns new object each render,
    Naive UI's Object.assign sees a fresh value every time,
    internal pagination state resets, mergedItemCountRef → undefined -->
<n-data-table :pagination="getPaginationConfig()" ...>
```

**The `:key="paginationVersion"` trick**: increment `paginationVersion.value++` after loading new data to force Naive UI to fully re-render the table and re-read the pagination config.

## Why This Works

Naive UI's `Object.assign({}, props.pagination)` runs **at render time** (inside the component's `setup()`), not at prop-receive time. So every time the `n-data-table` component re-renders, `Object.assign` re-executes and picks up the **current** value of `paginationConfig.total`.

Our `items.value = data.items` (a reactive ref assignment) **triggers a component re-render**. During that re-render, `Object.assign({}, paginationConfig)` re-runs and reads the **new** `paginationConfig.total` value — which we just updated via `paginationConfig.total = total.value` in `loadData()`.

**Causality chain**: `loadData()` → `items.value = data.items` (re-render) → `Object.assign({}, paginationConfig)` (reads fresh total) → Naive UI updates pagination UI.

If `total` is a string (e.g. API returns `"28"`), Naive UI string-coerces it. Always pass a number: `paginationConfig.total = Number(data.total)`.

## Why Individual refs?

`page`/`pageSize`/`total` as separate `ref()`s are necessary because:
1. **`total`**: Must be manually synced to `paginationConfig.total` after each `loadData()` — `paginationConfig.total` itself is **not reactive**, so changing it doesn't trigger re-renders. The re-render is triggered by `items.value = data.items` (a ref assignment).
2. **`page`/`pageSize`**: Passed into `paginationConfig.onChange` / `paginationConfig.onUpdatePageSize` as closure values. Keeping them as refs ensures `loadData()` always reads the current page number when called.

The **manual sync approach** (above) requires remembering to update `paginationConfig.total` in every code path. The **watchEffect approach** (below) is more robust:

```js
import { ref, watchEffect } from 'vue'

const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const paginationVersion = ref(0)

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

// watchEffect auto-syncs whenever refs change — no manual sync needed
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
  paginationVersion.value++  // force Naive UI to re-render
}
```

Template: `<n-data-table :pagination="paginationConfig" :key="paginationVersion" :remote="true">`

## Critical: Sync Order in loadData()

```js
const loadData = async () => {
  const resp = await fetch(`/api/data?page=${page.value}&page_size=${pageSize.value}`)
  const data = await resp.json()
  items.value = data.items          // 1. triggers n-data-table re-render
  total.value = Number(data.total) // 2. update ref (used by next loadData call)
  paginationConfig.total = total.value // 3. update plain object (Naive UI reads this on re-render)
}
```

Do NOT put `paginationConfig.total = total.value` before `items.value = data.items` — the order matters for triggering the re-render first.

## Common Mistakes That Don't Work
1. `const pagination = reactive({...})` — reactive proxy loses reactivity through `Object.assign`
2. `const pagination = ref({...})` — Vue auto-unwraps in template but Naive UI still gets non-reactive inner object
3. `const paginationConfig = computed(() => ({...}))` — creates new object reference on each access, breaks Naive UI's internal state
4. Passing `paginationConfig` as a computed without manual sync — same problem
5. **`watchEffect(() => paginationConfig.total = total.value)` without also updating `items.value`** — `paginationConfig.total` mutation is not reactive by itself; the re-render only fires when a **ref** (like `items.value`) is assigned, not when a plain object property is mutated

## Applicable
- Naive UI `n-data-table` with `remote=true` pagination
- Naive UI version: 2.43.2 / 2.44.1
- Vue 3 Composition API
- Multiple `n-data-table` on the same page — each needs its own separate `paginationConfig` instance and its own set of `page`/`pageSize`/`total` refs. Do NOT reuse a single config object across tables.

## Verification
After applying fix, browser console should show `{total: 28, activePage: 1, buttonCount: N}` where `buttonCount >= 4` (prev/1/[2]/next). If `buttonCount` is still 3, the fix was not applied correctly — check that:
1. `paginationConfig` is a plain object (not `reactive()` or `ref()`)
2. `paginationConfig.total` is being updated in `loadData()`
3. `onChange` and `onUpdatePageSize` are both syncing `paginationConfig.page`

## Related
- `naive-ui-pagination-debugging` — original debugging skill with more details on investigation
