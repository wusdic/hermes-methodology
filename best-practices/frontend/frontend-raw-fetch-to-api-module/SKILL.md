---
name: frontend-raw-fetch-to-api-module
description: Vue 组件 raw fetch → API 模块迁移方法论：扫描、验证路径、修复 export/import 不匹配、构建验证
tags: [vue, frontend, api, fetch, element-plus]
version: 1.0
---

# Vue 组件 Raw Fetch → API 模块迁移方法论

## 触发条件
当需要将 Vue 组件中的原生 `fetch()` 调用替换为统一 API 模块时使用。

## 典型问题链
1. 组件用 `fetch('/api/v1/...')` 直连后端
2. 需要改用 `@/api/xxx` 模块统一管理
3. 迁移时发现模块导出方式与 import 语句不匹配 → 构建报错

## 标准化流程

### Step 1: 扫描所有 raw fetch
```bash
grep -rn "fetch(" frontend/src/features/
```
过滤掉 `import` 行和注释行。

### Step 2: 验证 API 路径实际可用性
必须用实际请求验证，不能只看代码：
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123456"}' | jq -r .access_token)
curl -s http://localhost:8000/api/v1/assets/device?page=1&page_size=1 \
  -H "Authorization: Bearer $TOKEN"
```

### Step 3: 检查目标 API 模块的导出方式
```bash
grep "^export" frontend/src/api/xxx.js
```
常见两种导出方式：
- `export const name = {...}` → 用 `import { name }`
- `export default name` → 用 `import name`

如果模块是 `export default`，但组件用 `import { name }`，构建报错：`"name" is not exported by`。

### Step 4: 检查 API 模块的具体命名空间结构
API 模块不一定按预期组织：
```bash
grep "^export" frontend/src/api/monitoring.js
```
输出可能是 `export const alerts = {...}`，而不是 `export const monitoring = { alerts: {...} }`。

### Step 5: 更新组件 import
修复导出方式后（如需要），按实际结构 import：
```js
import { assets } from '@/api/assets'           // 命名导出
import { automation } from '@/api/automation'   // 需改 automation.js 为命名导出
import { alerts } from '@/api/monitoring'        // 直接取 alerts，不是 monitoring.alerts
import { ai } from '@/api/ai'                    // 如模块不存在则新建
```

### Step 6: 重构 fetch 调用
```js
// Before (raw fetch)
const res = await fetch('/api/v1/assets/device', {
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
})
const data = (await res.json()).data

// After (API module, request.js interceptor handles token)
const res = await assets.getList({ page: 1, page_size: 1 })
const data = res?.data  // request 拦截器已处理包装格式
```

### Step 7: 立即构建验证
```bash
cd frontend && npm run build 2>&1 | grep -E "error|not exported|not imported"
```
构建报错是最快的反馈，不要跳过。

## 常见陷阱

### 陷阱 1: request.js 拦截器响应格式不统一
`request.js` 拦截器对不同响应格式处理不同：
- 有 `items/total` 的 → 返回 `{ data: res }`
- 有 `code/data` 的 → 返回 `res`（保持原样）
- 直接是数组的 → 返回 `{ data: { items: res, total: res.length } }`

组件取值需兼容：
```js
const data = res?.data
const items = data?.items || data
```

### 陷阱 2: 新 API 模块不存在
`ai.js`、`aiops.js` 等可能不存在。需要新建：
```js
// frontend/src/api/ai.js
import request from './request'
export const ai = {
  analyze: (data) => request.post('/ai/analyze', data),
  getAnalyzeHistory: (params) => request.get('/aiops/analysis/history', { params }),
}
```

### 陷阱 3: 后端路由 prefix 与预期不符
后端 `router = APIRouter(prefix="/api/v1/ai")` → 实际路径是 `/api/v1/ai/analyze`，不是 `/ai/analyze`。不要猜测，用 curl 实际验证。

### 陷阱 4: API 模块缺少所需方法
如 `monitoringEvent.alerts` 已有 `acknowledge/resolve/close`，但没有 `transfer`。直接添加：
```js
// frontend/src/features/monitoring-event/api/index.js
transfer: (id, data) => request.post(`/monitoring/alerts/${id}/transfer`, data),
```

## 验证清单
- [ ] 所有 raw fetch 已替换为 API 模块
- [ ] `npm run build` 无错误
- [ ] curl 验证实际路径返回 200
- [ ] import/export 方式匹配
- [ ] request.js 拦截器兼容新响应格式
