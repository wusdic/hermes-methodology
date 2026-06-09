---
name: naive-ui-data-table-pagination-debugging
description: Debug n-data-table remote pagination showing only page 1 — root cause is Naive UI's Object.assign stripping Vue reactivity proxies
tags: [naive-ui, pagination, n-data-table, remote-pagination, vue3]
---

# Naive UI n-data-table Pagination Debugging

## Problem
`n-data-table` with `remote` mode pagination only shows page 1. No page 2 button. DOM inspection reveals `mergedItemCountRef` returns `undefined` — total is not tracked.

## Root Cause
Naive UI internally does `Object.assign({}, props.pagination)` to copy pagination props. This flattens the object but **strips reactive/Proxy wrappers** from both `reactive()` and `ref()` objects. The `mergedItemCountRef` computed internally cannot track the `total` property through the assigned copy.

This is a Naive UI internal behavior, NOT a Vue 3 reactivity issue. Both `reactive()` and `ref()` approaches fail identically.

## Verified Solution
Use a **plain JS object** with **individual `ref()` values** for each pagination field. Manually sync both directions:

```js
// Individual refs for each field
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// Plain object — NOT reactive, passed directly to n-data-table
const paginationConfig = {
  page: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (p) => {
    page.value = p
    paginationConfig.page = p
    loadData()  // reload with new page
  },
  onUpdatePageSize: (size) => {
    page.value = 1
    paginationConfig.page = 1
    pageSize.value = size
    paginationConfig.pageSize = size
    paginationConfig.total = total.value
    loadData()  // reload from page 1
  }
}
```

In `loadData()`:
```js
total.value = data.total
paginationConfig.total = data.total  // MUST sync both
```

In template:
```html
<n-data-table :pagination="paginationConfig" ... />
```

## Why This Works
- Naive UI receives a plain JS object (no Proxy, no Vue reactivity wrapper)
- `Object.assign({}, plainObject)` creates a proper shallow copy Naive UI can use
- `mergedItemCountRef` can track the `total` property on the copied object
- Individual `ref()` values let Vue components reactively update UI
- Manual sync ensures both the plain config object and the reactive refs stay in sync

## What DOES NOT Work
- `reactive({ page: 1, pageSize: 20, total: 0, ... })` — Proxy stripped by Object.assign
- `ref({ page: 1, pageSize: 20, total: 0, ... })` — Vue unwraps in template but Object.assign still gets non-reactive
- `computed(() => ({ ... }))` — Creates new object on every access, Naive UI loses internal state

## Related Skills
- `naive-ui-pagination-debugging` — older, recommends `getPaginationRefs` approach
- `naive-ui-remote-pagination-workaround` — workaround without explaining root cause
- This skill supersedes those with the actual root cause explanation
