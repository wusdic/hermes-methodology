---
name: naive-ui-pagination-remote-workaround
description: Naive UI n-data-table remote 模式分页只显示1页的 bug — getPaginationConfig() 纯对象函数方案
version: 5.0.0
category: frontend
tags: [naive-ui, vue3, pagination, n-data-table, remote, workaround]
metadata:
  hermes:
    related_skills: [naive-ui-debugging, itops-platform-debugging]
---

# Naive UI n-data-table 远程分页 Bug — 根解方案 v5

## 症状

`n-data-table` 组件开启 `remote` 模式后，分页只显示"上一页/1/下一页"（3个按钮），即使 total=28、pageSize=20 有2页数据，第2页按钮也不出现。浏览器控制台 `JSON.stringify({total, activePage, buttonCount})` → `{"total":"28","activePage":"1","buttonCount":3}`。

## 根因：Object.assign 丢失 Vue 响应式 + 缺少 :remote + 缺少 :key

有**三个**独立陷阱，任何一个不满足都会导致分页只显示第1页：

1. **Object.assign 陷阱**：`n-data-table` 内部执行 `Object.assign({}, props.pagination)` 复制分页配置，然后监听副本。
   - `reactive({...})` → `Object.assign` 得到纯对象，Vue reactivity 追踪丢失，`mergedItemCountRef` 返回 `undefined`
   - `ref({...})` 整体包装 → Vue auto-unwrap 后 Naive UI 收到普通对象，`Object.assign` 仍追踪不到
   - **`getPaginationConfig()` 每次返回新对象** → ❌ 失败！回调写到返回的新对象上，但 Naive UI 监听的是 `Object.assign` 后的另一个副本

2. **`:remote="true"` 缺失陷阱**：这是本次调试中新发现的！即使正确实现了共享对象，`n-data-table` **如果不显式声明 `:remote="true"`**，Naive UI 会使用本地分页逻辑，完全忽略 `onChange`/`onUpdatePageSize` 回调，导致分页控件不工作。devices.vue 有 `:remote="true"` 所以分页正常；logs.vue 之前没有所以不工作。**必须显式声明！**

3. **`:key` 绑定缺失陷阱**：Naive UI 的 `Object.assign` 拷贝发生在组件挂载时。如果不绑定 `:key="paginationVersion"`，Naive UI 不会重新读取更新后的 `itemCount`/`pageCount` 值，因为 Vue 的响应式系统没有触发 Naive UI 内部重新渲染。**必须在每次数据更新后 `paginationVersion.value++`** 触发重新挂载。

## ✅ 正确方案：共享纯 JS 对象 + version ref

关键洞察：Naive UI 的 `Object.assign` 需要作用在**同一个对象引用**上，回调里的写操作才能被 Naive UI 内部正确追踪。

```javascript
import { ref } from 'vue'

// Step 1: 分离的 ref（驱动 API 调用和响应式状态）
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const paginationVersion = ref(0)  // 触发重渲染用

// Step 2: 在 getPaginationConfig() 之前声明共享对象（TDZ 注意！）
const paginationConfig = {
  page: 1,
  pageSize: 20,
  itemCount: 0,
  pageCount: 1,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  prefix: ({ itemCount }) => `共 ${itemCount} 条`,
  onChange: (p) => {
    page.value = p
    paginationConfig.page = p
    paginationVersion.value++
    loadData()
  },
  onUpdatePageSize: (size) => {
    pageSize.value = size
    page.value = 1
    paginationConfig.pageSize = size
    paginationConfig.page = 1
    paginationVersion.value++
    loadData()
  }
}

// Step 3: getPaginationConfig() 返回同一个引用（不是新对象！）
function getPaginationConfig() {
  paginationConfig.itemCount = total.value
  paginationConfig.pageCount = Math.max(1, Math.ceil((total.value || 0) / (pageSize.value || 1)))
  return paginationConfig
}

// Step 4: loadData() 后同时更新 ref 和共享对象
async function loadData() {
  const res = await fetch(`/api/list?page=${page.value}&page_size=${pageSize.value}`)
  const data = await res.json()
  total.value = data.total || 0
  paginationConfig.itemCount = total.value           // ← 必须同步！
  paginationConfig.pageCount = Math.max(1, Math.ceil(total.value / pageSize.value))
}

// Step 5: 模板中必须同时满足三个要素
// <n-data-table
//   :pagination="getPaginationConfig()"
//   :key="paginationVersion"        ← 触发 Naive UI 重新读取 itemCount/pageCount
//   :remote="true"                  ← 开启远程分页模式（缺少此属性则完全不工作！）
//   :row-key="row => row.id"
//   ...>
```

### 为什么共享引用有效

```
paginationConfig (plain object, 同一个引用)
    ↓
getPaginationConfig() 返回 paginationConfig
    ↓
Naive UI 内部: Object.assign({}, props.pagination) — 复制引用指向的对象
    ↓
Naive UI 内部 watch 监听同一个对象引用
    ↓
onChange 回调写入: paginationConfig.page = p → Naive UI 能看到变化 ✅
```

### ⚠️ TDZ（Temporal Dead Zone）陷阱

`paginationConfig` 必须在 `getPaginationConfig()` **之前**声明！如果在 `onChange`/`onUpdatePageSize` 回调里引用 `paginationConfig` 但这个变量还没声明过：

```javascript
// ❌ 错误: paginationConfig 在声明前被引用（TDZ）
const paginationConfig = {  // 这里声明
  onChange: (p) => {
    paginationConfig.page = p  // TDZ! 第一次 onChange 触发时还没执行到这里
  }
}
const getPaginationConfig = () => paginationConfig  // 这里引用了 paginationConfig
```

正确做法：在 `getPaginationConfig()` 函数定义**之前**声明 `const paginationConfig = {...}`，这样无论 `getPaginationConfig()` 何时被首次调用，`paginationConfig` 都已存在于作用域中。

### 回调放在对象外部（稳定引用）

```javascript
// ✅ callbacks 定义在 paginationConfig 之外（稳定引用）
const handlePageChange = (p) => {
  page.value = p
  paginationConfig.page = p
  paginationVersion.value++
  loadData()
}
const handlePageSizeChange = (size) => {
  pageSize.value = size
  paginationConfig.pageSize = size
  page.value = 1
  paginationConfig.page = 1
  paginationVersion.value++
  loadData()
}

const paginationConfig = {
  onChange: handlePageChange,
  onUpdatePageSize: handlePageSizeChange,
  // ... 其他属性
}
```

### 多表分页（一个页面多个 n-data-table）

每个表用独立的 ref 组和独立的 getPaginationConfig 函数：

```javascript
// 设备表
const devPage = ref(1)
const devPageSize = ref(20)
const devTotal = ref(0)
function getDevPagination() { return { page: devPage.value, pageSize: devPageSize.value, itemCount: devTotal.value, ... } }

// 告警表
const alertPage = ref(1)
const alertPageSize = ref(20)
const alertTotal = ref(0)
function getAlertPagination() { return { page: alertPage.value, pageSize: alertPageSize.value, itemCount: alertTotal.value, ... } }
```

### ⚠️ 加载函数末尾必须 `paginationVersion.value++`

即使 `:key` 绑定和共享对象都正确，**如果 loader 末尾没有 `paginationVersion.value++`，分页也不会更新**。这是最容易被遗漏的一步。

logs.vue 有 `:key="paginationVersion"` 也有正确的共享对象，但4个 loader（operation/system/alertAudit/collection）全部漏掉了这行，导致 78 页数据加载后仍然只显示3个按钮。

**每个加载函数必须在数据赋值后调用**：

```javascript
async function loadData() {
  try {
    const res = await fetch(`/api/list?page=${page.value}&page_size=${pageSize.value}`)
    const data = await res.json()
    total.value = data.total || 0
    paginationConfig.itemCount = total.value
    paginationConfig.pageCount = Math.max(1, Math.ceil(total.value / pageSize.value))
    paginationVersion.value++  // ← 必须！否则 Naive UI 不重新渲染分页控件
  } catch (err) {
    console.error('loadData failed:', err)
  }
}
```

当页面有多个 loader（如操作日志/系统日志/告警审计/采集日志4个），**每个都要加**。onChange/onUpdatePageSize 回调里也要 `paginationVersion.value++`。

**实战案例**：
- logs.vue 的 `loadOperationLogs()`、`loadSystemLogs()`、`loadAlertAuditLogs()`、`loadCollectionLogs()` 4个函数全部在 try 块末尾加了 `logPaginationVersion.value++`
- 浏览器验证：`JSON.stringify({total, activePage, buttonCount})` → `{"total":78,"activePage":1,"buttonCount":9}`，显示 `, 1, 2, 3, 4, 5, 6, 7, , 78,` ✅

### ❌ 不要做的事

- ❌ **不要混淆 `itemCount` 和 `total`**：Naive UI `n-data-table` 的分页对象读 `itemCount`（总条数），不是 `total`。如果传了 `total` 但没传 `itemCount`，Naive UI 内部 `mergedItemCountRef` 返回 `undefined`，分页控件无法计算页数，只显示第1页。
- ❌ **不要忘记 `:remote="true"`**：这是最容易被忽略的！没有这个属性，Naive UI 使用本地分页逻辑，`onChange`/`onUpdatePageSize` 根本不会被调用。调试时先确认 devtools 中 `n-data-table` 是否收到了正确的 pagination props，再检查是否有 `:remote="true"`。
- ❌ 不要用 `reactive({...})` 包装分页对象（Object.assign 丢失响应式）
- ❌ 不要用 `ref({...})` 包装整个分页对象（Naive UI 内部 watch 仍追踪不到）
- ❌ 不要用 `getPaginationConfig()` 内 `return {...}` 每次返回新对象（回调写到了错误的引用上）
- ❌ **不要只加 `:key` 不加 `:remote="true"`**：两个都要有，缺一不可
- ❌ **警惕 patch 重复声明**：多行 patch 可能意外引入重复的 `const page = ref(1)` 等声明，build 时不会报错但运行时行为异常（如 paginationConfig 中引用的是旧的 ref）。**检查源文件确认无重复声明。**
- ❌ loadData 后忘记更新 `total.value`
- ❌ **忘记设置 `pageCount`**：Naive UI 需要 `pageCount`（总页数）来渲染分页按钮。如果只传 `itemCount` 而不传 `pageCount`，Naive UI 会尝试自己计算但可能不准确。建议同时传：`pageCount: Math.max(1, Math.ceil((total.value || 0) / (pageSize.value || 1)))`

### 已知 bug：Fallback 分页

如果 stats API 失败（如 `/api/v1/assets/stats` 返回非 200），代码 fallback 到 `page=1&page_size=100` 全量加载。这个 fallback 会绕过正确的分页逻辑，导致页面只显示 100 条且分页控件显示 total=100 而非真实 total。修复：确保 stats API 正确返回，或在 fallback 中也更新正确的 total。

## 告警统计独立 API 设计

问题：统计（critical/warning/info/active 数量）不能从当前页数据计算（当 page>1 时当前页不足）。

解法：后端提供 `stats_only=1` 参数，返回聚合统计不分页。

```python
# GET /api/v1/monitoring/alerts?stats_only=1
# 返回: {"total": 28, "critical": 2, "warning": 5, "info": 21, "active": 8}
```

前端独立调用：
```javascript
async function loadAlertStats() {
  const res = await fetch('/api/v1/monitoring/alerts?stats_only=1')
  const data = await res.json()
  alertStats.value = {
    critical: data.critical || 0,
    warning: data.warning || 0,
    info: data.info || 0,
    active: data.active || 0
  }
}
```
