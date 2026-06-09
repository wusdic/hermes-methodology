---
name: element-plus-table-debugging
description: Debug Element Plus el-table rendering issues — columns show no content despite API returning data. Covers the :="col" anti-pattern, column type mismatches, and async data timing issues.
category: frontend
tags: [element-plus, vue3, el-table, debugging]
version: 1.0.0
created: 2026-05-27
---

# Element Plus Table Debugging

## Pattern A: Column rendering returns empty despite data existing

**Symptoms:** Table has correct number of rows but every cell is empty. API returns data correctly. No JS errors.

**Root Cause:** `el-table-column` does NOT support Vue 2 render function pattern. `:="col"` spread syntax is ignored by Element Plus.

**Wrong code (does NOT work):**
```vue
<el-table :data="scanResults">
  <el-table-column v-for="col in resultColumns" :key="col.key" :="col" />
</el-table>
```

Where `resultColumns` contains `{ title: 'IP', key: 'ip', render: (row) => h('span', row.ip) }` — the `render` function is silently ignored.

**Correct code (explicit props + scoped slots):**
```vue
<el-table :data="scanResults">
  <el-table-column prop="ip" label="IP地址" width="150" />
  <el-table-column label="主机名" width="150">
    <template #default="{ row }">{{ row.hostname || '-' }}</template>
  </el-table-column>
  <el-table-column label="状态" width="80">
    <template #default="{ row }">
      <el-tag :type="row.status === 'up' ? 'success' : 'info'" size="small">
        {{ row.status === 'up' ? '在线' : '离线' }}
      </el-tag>
    </template>
  </el-table-column>
</el-table>
```

**Why it fails:** Element Plus `el-table-column` in Vue 3 does not accept a `render` option via prop spreading. Only `prop` (for simple data binding) or `#default` scoped slot (for custom rendering) work.

**Same issue manifests as:**
- `v-for="col in columns" :="col"` — all columns render empty
- `render: (row) => h(...)` in column definition objects — silently ignored
- `h('el-table-column', { props: col })` — not how Element Plus works

**Verification:** Check browser console for no errors, then inspect DOM:
```js
// Should show <div class="cell"><!----></div> for each empty cell
document.querySelector('.el-table__body-wrapper tr:first-child td').innerHTML
// Returns: "<div class=\"cell\"><!----></div>" — vfor rendered but content empty
```

---

## Pattern B: Column shows data but wrong field name

**Symptoms:** Column has content but shows "undefined" or wrong value.

**Root Cause:** API returns a different field name than what the column definition uses.

**Example:** API returns `category` but column uses `device_type`:
```js
// API: { ip: "10.0.0.1", category: "server", ... }
// Frontend column definition:
{ title: '设备类型', key: 'device_type' }  // WRONG — shows undefined
```

**Fix:** Match the exact field name from API response. Use curl to verify:
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin@123456"}' | \
  python3 -c "import sys,json; t=json.load(sys.stdin)['data']['token']; \
  print(json.dumps(json.loads(subprocess.getoutput(f'curl -s -H \"Authorization: Bearer {t}\" http://localhost:8000/api/v1/...')), indent=2))"
```

---

## Pattern C: Table renders before async data arrives

**Symptoms:** Table shows "暂无数据" even though API works in curl.

**Root Cause:** Table renders before the `fetch()` completes. `v-if="data.length > 0"` prevents any DOM from being created, leaving no mount point for Vue's reactivity.

**Fix:** Always render the table container, use `v-if` only on the inner content:
```vue
<el-table :data="scanResults" v-if="scanResults.length > 0">
```
OR use skeleton/loading state:
```vue
<el-skeleton :rows="5" animated v-if="loading" />
<el-table :data="scanResults" v-else />
```

---

## Red Flags (stop and investigate before continuing)

1. **`:="col"` or `:prop="col"` in any table** — 100% will cause empty columns in production
2. **`render:` function in column definition** — Element Plus ignores it silently
3. **Field name in template doesn't match API response** — use curl to verify actual field names
4. **Table uses `v-model:selected`** — confirm Element Plus supports it for your use case
5. **Pagination on local data** — verify the table component actually supports it natively

## Verification Checklist

After any table fix:
- [ ] Browser: table has correct row count (not just 1 empty row)
- [ ] Browser: each cell has actual text content (not `<!---->`)
- [ ] Browser: custom renders (tags, buttons) show correct values
- [ ] API curl: actual response field names match what template uses
- [ ] Build: `npm run build` succeeds with no errors
