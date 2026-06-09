---
name: element-plus-debugging
description: Element Plus 组件调试经验汇总 — 图标名陷阱、常见报错、组件使用雷区
tags: [frontend, element-plus, vue3]
version: 2026-05-29
---

# Element Plus 调试经验

## 图标名陷阱（已验证错误）

Element Plus icons-vue 中以下名字**不存在**，必须用别名：

| 错误名 | 正确名 | 来源 |
|--------|--------|------|
| `Magic` | `MagicStick` | 文档和实际导出名不一致 |
| `WarnTriangleFilled` | `WarningFilled` | fill 型图标后缀是 Filled 不是 Filled |

其他常见 fill 型图标后缀规律：`-Filled`（如 `CircleCheckFilled`, `CloseBold` 等）

**验证方法**：`grep -r "export" node_modules/@element-plus/icons-vue/dist/es/index.js`

## 常见 Component 报错

### "XXX is not exported by @element-plus/icons-vue"
**根因**：导入的是中文文档/旧版本写法，实际包中不存在该名字。
**修复**：去 `node_modules` 实际文件查导出列表。

### el-table-column 渲染异常
常见于 `v-for` 动态生成的列，prop 和 label 拼写错误不报错但列不显示。

## 响应拦截器与 API 格式契约（ITOps Platform 特有问题）

**问题**：后端部分接口返回 `{items, total}`（直接数组+总数），拦截器 `res.data` 后组件用 `res.data.items` 取值，得到 `undefined`。

**受影响接口**：告警列表 `/monitoring/alerts`、事件列表 `/events` 等所有返回 `{items, total}` 的分页接口。

**修复**（`frontend/src/api/request.js` 拦截器）：
```javascript
// 对 {items, total} 格式统一包装为 {data: {items, total}}
if (res.data && Array.isArray(res.data.items)) {
  return { data: res }
}
```

**验证**：打开浏览器 DevTools → Network → 检查响应 body 是否需要 `.data` 再次取值才能拿到 `items`。

## API 路由不一致（ITOps Platform 特殊问题）

| 功能 | 实际路径 | 注意事项 |
|------|----------|----------|
| 告警统计 | `/api/v1/monitoring/alerts/statistics` | |
| 事件列表 | `/api/v1/events` | **独立 router**，不是 `/monitoring/events` |
| 指标历史 | `/api/v1/monitoring/metrics/history` | metrics 挂载在 monitoring 下 |
| 设备列表 | `/api/v1/devices` | |

## Naive UI → Element Plus 迁移注意

（来自本项目迁移经验）

- `NDataTable` → `ElTable`（+ `ElTableColumn`）
- `NPagination` → `ElPagination`（注意 `current-change` vs `@current-change`）
- `NSelect` → `ElSelect`（`filterable` 写在标签上，非 options）
- `NInput` → `ElInput`
- `NSpace` → `ElSpace`
- 图表：ECharts 直接用 `vue-echarts`，不依赖 UI 库

## 验证步骤

1. `npm run build` 无报错
2. 浏览器 DevTools Console 无红字
3. Network 确认 API 返回 200
4. 确认页面有数据（非 loading/空状态）
