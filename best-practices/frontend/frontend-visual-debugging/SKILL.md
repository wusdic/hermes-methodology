---
name: frontend-visual-debugging
description: 前端视觉/渲染类bug系统性调试方法论——页面空白、图表不显示、表格数据为空、组件样式异常。6层验证从后端API到浏览器像素。
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [frontend, debugging, vue, echarts, element-plus, visual-bug]
    related_skills: [systematic-debugging, naive-ui-debugging]
---

# Frontend Visual Bug系统性调试方法论

## 触发条件

前端页面出现以下症状时立即启用本方法论：
- 页面空白 / 组件不渲染 / 数据加载后消失
- 图表（ECharts/Chart.js）显示异常或空白
- 表格有行但列内容为空
- 组件样式错位、颜色异常
- 已知后端 API 返回正确数据，但前端显示不对
- 用户反馈"页面看着不对"但控制台无报错

## 核心原则

### 原则1：分层验证，从下往上
```
数据库 → 后端API → 前端网络响应 → Vue响应式状态 → DOM渲染 → 视觉呈现
```
每层单独验证，不能跳级。代码逻辑正确 ≠ 运行时正确。

### 原则2：浏览器是最终真相
- `npm run build` 成功 ≠ 功能正确
- 代码逻辑推演 ≠ 运行时行为
- Browser DevTools 的 Elements 和 Console 是 ground truth
- 始终在浏览器中验证，不在代码层面"自证正确"

### 原则3：API真实性是第一约束（绝对禁止）
**绝对禁止**：前端调用后端不存在的接口。
- 所有 API 调用必须在 `curl` 中验证存在后才能写进前端代码
- `npm run build` 成功 ≠ 接口存在
- 代码能跑起来 ≠ 接口存在
- 页面"看起来有数据" ≠ 接口存在（可能是旧缓存、mock数据、默认值）
- **每一行 `request({ url: '...' })` 都必须对应一个真实可调的 curl 命令**
- 发现接口不存在时：立即在 **后端** 补上接口，或改为调用已存在的接口，**不允许绕过或留待后续**

违反此原则的后果（已发生）：
- 页面长期显示空白，total=0, online=0，没有人发现
- 用户无法使用核心功能（监控中心设备页）
- 修复时还需要额外交叉验证其他页面是否也有同样问题

### 原则4：单次改动最小化 + 验证即停止

---

## 诊断流程（6步）

### 第1步：后端 API 直接验证（最关键）
不过前端，用 curl/httpx 直接打后端接口。

```bash
# 1. 登录获取 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 2. 调用目标 API
curl -s http://localhost:8000/api/v1/xxx \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**验证点**：
- [ ] HTTP 状态码是 200（不是 500/401/503）
- [ ] 响应体 JSON 结构是否符合前端期望的字段名
- [ ] 数据条数和内容是否和数据库一致
- [ ] 字段名是 `level` 还是 `severity`，是 `status` 还是 `state`

### 第2步：前端网络响应验证
打开浏览器 DevTools → Network，找到对应请求：
- [ ] Response 是否和 curl 结果一致
- [ ] 字段名是否和 Vue 代码中引用的字段名完全匹配
- [ ] 前端代码里有没有 `.data` 或 `.json()` 重复提取导致数据嵌套

### 第3步：Vue 响应式状态验证
Browser Console 执行：
```javascript
// 找到表格数据（假设表格 ref="tableRef"）
document.querySelector('.el-table__body-wrapper tr').length  // 表格行数

// 打印关键 API 的原始响应（在 Network 面板 Copy as Fetch）
// 在 Console 里用相同的 URL + header 发请求看原始返回
```

### 第4步：DOM 存在性 + 内容验证
```javascript
// 有没有这个 DOM 节点
document.querySelectorAll('canvas').length                      // 图表 canvas
document.querySelectorAll('.el-table__body-wrapper tr').length  // 表格行数
document.querySelectorAll('.el-progress').length               // 进度条

// 有 DOM 节点但内容为空 = 渲染问题
document.querySelector('.el-table__body-wrapper tr td .cell').innerHTML

// 有数据但不可见 = CSS 问题（颜色对比度）
getComputedStyle(document.querySelector('.stat-value')).color
getComputedStyle(document.querySelector('.stat-value')).backgroundColor

// 表格：逐列检查内容（cell 里有内容还是只有 <!---->）
document.querySelectorAll('.el-table__body tr td:nth-child(2) .cell').forEach(
  el => console.log(el.textContent.trim())
)
```

### 第5步：图表专项验证
```javascript
// 图表容器尺寸（clientWidth=0 会导致 canvas 空白）
document.querySelector('.chart-container')?.clientWidth
document.querySelector('.chart-container')?.clientHeight

// echarts 实例是否存在
document.querySelector('.chart-container')?.__echarts_instance__

// 如果用了 CDN：确认 echarts 全局对象存在
window.echarts?.version

// 构建产物里是否包含 echarts（grep 方式）
// 在 Network 面板找主 JS，curl 或下载后 grep "echarts"
```

### 第6步：视觉截图验证
最后一步，必须截图确认实际视觉呈现：
- 截图能看到文字颜色对比度（代码里看不到）
- 进度条百分比数字（`:percentage="0"` 时不显示文字）
- 图表配色是否和代码配置一致
- 截图和 DOM 检查结论必须互相印证

---

## 常见根因模式

### 模式A：数据获取层
| 症状 | 常见原因 | 验证方法 |
|---|---|---|
| 表格有行但空 | API 字段名和前端引用不匹配 | curl 对比字段名 |
| 数据全部为0/空 | `res.data.data` vs `res.data` 提取层数错 | Console 打印实际响应 |
| 某条数据缺失 | pagination page/page_size 参数错误 | 检查前端传参 |
| 页面空白 | API 返回 500 但前端没有报错提示 | Network 面板检查状态码 |

### 模式B：图表渲染层
| 症状 | 常见原因 | 验证方法 |
|---|---|---|
| Canvas 为空 | 容器 `clientWidth/Height` 为 0（父元素隐藏或尺寸为0） | Console 查 `el.clientWidth` |
| Canvas 存在但无图 | echarts 实例未初始化或数据为空 | 查 `.__echarts_instance__` |
| CDN 只在首次生效 | 构建覆盖 dist/index.html | 确认 CDN 在源文件而非 dist |
| 图表空白 | Vite 懒加载分包导致 echarts 未被打包 | grep 构建产物是否包含 echarts |
| 图不刷新 | 数据变了但没有调用 `chart.setOption()` | 监听数据变化后的 DOM |

### 模式C：表格渲染层
| 症状 | 常见原因 | 验证方法 |
|---|---|---|
| 表格有行但列空 | `el-table-column` 的 `:="col"` 展开不支持 render 函数 | 改用 `<template #default="{row}">` |
| 字段名错 | API 返回 `level`，前端用 `severity` | 对比 curl 响应和前端模板 |
| 日期显示不完整 | `slice(0,16)` 遇到 UTC 时间被截断 | `replace('T',' ').slice(0,16)` |
| 状态文字错误 | 后端返回英文，前端用中文映射表缺失 | 检查 API 原始值 |

### 模式D：样式/布局层
| 症状 | 常见原因 | 验证方法 |
|---|---|---|
| 文字不可见 | 字体颜色和背景色对比度低 | `getComputedStyle().color` |
| 进度条百分比空白 | `:percentage="0"` 时 el-progress 不显示文字 | 确认数据范围非零 |
| 组件尺寸异常 | `el-card` 的 `size` 属性用了非法值 | 检查 el-card 文档，删除 size 属性 |
| 布局错位 | CSS flex/grid 父容器没有 `display:flex` | DevTools 检查 Computed |

### 模式E：Vue 响应式机制
| 症状 | 常见原因 | 验证方法 |
|---|---|---|
| ref 是数组 | v-for 里的 `:ref="el => arr.push(el)"` 每次返回同一个变量 | Console 查 `arr.length` 和 `arr[0]` |
| 条件渲染后 DOM 丢失 | v-if="arr.length && arr[0].clientWidth" 中 arr[0] 是数组 | 打印实际值，不要假设类型 |
| 响应式数据不更新 | 直接赋值而非 `.value =` 或 `arr.push()` | 检查 ref 操作是否正确 |

### 模式F：需要推倒重写的信号
当遇到以下情况，停止修补丁，考虑重写这段代码：
| 信号 | 说明 | 行动 |
|---|---|---|
| 图表渲染用了 setTimeout 重试 3+ 次才成功 | 时序依赖，说明渲染时机没有从根本上解决 | 重写 init 逻辑，用 nextTick 或 ResizeObserver |
| 一个组件里有 5+ 个 `if (chart)` 判断 | 图表实例状态管理混乱 | 推倒重写，用 `reactive()` 统一管理 |
| 前端对 API 响应做了 3+ 层提取（`res.data.data.xxx`） | API 返回结构设计错误 | 和后端对齐正确的返回结构，在后端修复 |
| 表格列定义用了 render 函数但 el-table-column 不支持 | 框架机制理解错误 | 推倒重写，用 `<template #default="{row}">` 作用域插槽 |
| v-for 里的 `:ref` 导致 clientWidth=undefined | Vue ref 机制理解错误 | 推倒重写，用 `document.querySelector` 直接查 DOM |

---

## 验证检查清单（每个修复后必查）

每修复一个问题，必须按顺序完成以下全部验证：

```
[ ] 1. curl 直接调用后端 API → 数据正确
[ ] 2. DevTools Network 面板 → 前端收到正确响应  
[ ] 3. Browser Console 无 Error 级别输出
[ ] 4. document.querySelector 能找到目标 DOM
[ ] 5. DOM 节点内容正确（不是只有 <!---->）
[ ] 6. 截图确认视觉呈现符合预期
```

**如果发现新问题**：
- 新问题很可能是上一步修复的副作用 → 回滚本次修复，单独验证
- 或者新问题是历史遗留，先记录，修复当前目标后再处理
- 不要在同一个验证周期里修两个问题

---

## 防复发机制

### 约束1：API 真实性验证（强制）
```bash
# 写进前端代码之前，必须先用 curl 验证接口存在且返回正确结构
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123456"}' | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 验证目标 API
curl -s http://localhost:8000/api/v1/xxx -H "Authorization: Bearer $TOKEN"
```
- 每写一个 `request({ url: '/api/...' })` 前，必须有对应的 curl 验证记录
- 接口不存在 → 禁止绕过，必须在后端补上或改用已存在的接口
- **不依赖"构建成功"、"页面能打开"、"控制台没报错"来判断接口是否存在**
```
构建成功   → ✓ 语法正确
浏览器加载 → ✓ 依赖就绪
数据请求   → ✓ API 连通
DOM 渲染   → ✓ 组件挂载
视觉呈现   → ✓ 用户可见  ← 必须达到这一步
```

只有到最后一步才算验证完成。

### CDN 永久化（防止构建覆盖）
```
错误做法：手动修改 dist/index.html 加 CDN script
结果：npm run build 会覆盖 dist/index.html，CDN 丢失

正确做法：将 CDN 加到源文件 frontend/index.html
结果：每次构建产物自动包含 CDN script
```

### 条件渲染后必须验证 DOM 真的创建了
```javascript
// 错误写法：假设条件满足时 DOM 就存在
if (container.clientWidth > 0) {
  chart = echarts.init(container)  // container 可能还是 0
}

// 正确做法：用 nextTick + 重试上限
async function initCharts() {
  await nextTick()
  const container = document.querySelector('.chart-container')
  if (!container?.clientWidth) {
    console.warn('Chart container has no size, skipping init')
    return
  }
  chart = echarts.init(container)
}
```

---

## 调试工具箱

### 必用工具（按诊断场景）
| 工具 | 用途 |
|---|---|
| `curl` / `httpx` | 第1步：独立验证后端 API，不受前端代码干扰 |
| Browser DevTools Network | 第2步：确认前端收到的响应内容 |
| Browser DevTools Console | 第4步：读运行时状态、API 响应原始值 |
| Browser DevTools Elements | 第4步：查 DOM 节点、CSS 样式 |
| `vision` 截图 | 第6步：最终视觉验证（颜色对比度、进度条数字） |

### 有用但非必用
| 工具 | 用途 |
|---|---|
| Vue DevTools | 查看组件层级和响应式状态 |
| Browser Performance 面板 | 确认渲染时机问题 |
| Browser Application 面板 | 检查 localStorage 缓存 |

---

## 真实案例索引（来自 itops_platform 项目）

以下案例的完整调试过程保存在对话记录中：

| 案例 | 根因 | 验证方法 |
|---|---|---|
| 仪表盘图表空白（3层） | Vite懒加载未打包 + layoutRes.items未提取.data + ref数组导致clientWidth=undefined | Console查__echarts_instance__ + grep构建JS |
| 表格有行但列空 | API返回`level`，前端用`severity`；el-table-column不支持render函数展开 | curl对比字段名 + querySelector查cell内容 |
| ECharts CDN每次构建后失效 | dist/index.html被构建覆盖 | 确认CDN在源文件frontend/index.html |
| 统计卡片文字不可见 | CSS颜色对比度问题（getComputedStyle验证） | vision截图 + Console查computed style |
| 进度条百分比空白 | percentage=0时不显示el-progress__text | 截图确认 + 查el-progress DOM |

---

## 验证完成标准

当且仅当以下全部通过，才算问题真正解决：

- [ ] `curl` 直接调用 API 返回正确数据
- [ ] DevTools Network 面板显示前端收到正确响应
- [ ] Browser Console 无 Error 级别输出
- [ ] `document.querySelector` 能找到目标 DOM 且内容正确
- [ ] 截图确认视觉呈现符合预期

任意一项未通过，都不算修复完成。
