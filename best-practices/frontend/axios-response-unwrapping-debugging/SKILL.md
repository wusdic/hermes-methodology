---
name: axios-response-unwrapping-debugging
description: Vue+Axios data loading fails inside component despite working in browser console — caused by double-unwrapping of response data
---

# Axios Response Interceptor Unwrapping Debugging

## Trigger Conditions
Vue 3 + Axios project where API calls from the browser console work correctly but fail inside Vue components (table shows empty, stats show 0).

## The Problem Pattern

The response interceptor unwraps `response.data` and returns it:
```js
// request.js
response => {
  const res = response.data
  if (res.code === 200 || res.code === 0) {
    return res.data || res
  }
  if (res.items !== undefined) { return res }
  return res
}
```

Component code then tries to unwrap AGAIN:
```js
const res = await devices.getList({ page: 1, page_size: 500 })
const data = res.data || res.items || res  // WRONG: res IS already the data
hosts.value = Array.isArray(data) ? data : (data.items || [])
```

Result: `hosts.value = []` because `data.items` is `undefined`.

## Diagnostic Steps

### Step 1: Verify Backend API (always first)
```bash
curl -s "http://localhost:8000/api/v1/assets/device?page=1&page_size=3" \
  -H "Authorization: Bearer $TOKEN"
```
If this returns data, backend is fine.

### Step 2: Verify in Browser Console
```js
fetch('/api/v1/assets/device?page=1&page_size=3', {
  headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
}).then(r => r.json()).then(d => console.log('items:', d.items?.length, 'total:', d.total))
```

### Step 3: Add Debug Logging to Vue Component
```js
const res = await devices.getList({ page: 1, page_size: 500 })
console.log('[DEBUG] raw res:', JSON.stringify(res).slice(0, 200))
const data = res.data || res.items || res
console.log('[DEBUG] data:', Array.isArray(data) ? `array(${data.length})` : typeof data)
hosts.value = Array.isArray(data) ? data : (data.items || [])
```

## The Fix
```js
// Don't do: const data = res.data || res.items || res
// Do: interceptor already returned the data, use it directly
const data = res.items ? res : res  // res IS {items, total} or already the array
hosts.value = res.items ? (res.items || []) : (Array.isArray(res) ? res : [])
```

## Key Insight
The axios response interceptor has ALREADY unwrapped `response.data`. Component code must NOT call `.data` again. Check `frontend/src/api/request.js` to understand what the interceptor returns, then adjust extraction accordingly.
