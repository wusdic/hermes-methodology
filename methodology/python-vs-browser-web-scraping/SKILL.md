---
name: python-vs-browser-web-scraping
description: Python urllib/requests vs Hermes browser tool — when to use which for web scraping, and the critical JS-rendering gotcha with search engines
triggers:
  - "需要抓取网页数据"
  - "搜索引擎结果"
  - "curl 拿到了空 HTML"
---

# Python vs Browser 工具：网页抓取决策框架

## 触发条件
当你需要从互联网采集数据时，首先判断目标页面的性质，选择正确的工具。

## 核心判断

### Python urllib/requests 可以处理的（直接 HTTP）
- **静态 HTML 页面**：返回服务器直接生成的 HTML，无 JS 动态渲染
- **目标站点**：
  - 国内新闻站点（36kr、sina、ifeng、thepaper）
  - 国内数据交易所/政府网站（gzdata.com.cn）
  - 明确不依赖 JS 的 API 端点
- **特征**：直接 `view-source:` 或 `curl` 就能看到完整内容

### 必须用 browser 工具处理的（JS 动态渲染）
- **所有搜索引擎结果页**：Google、Bing、Baidu、DuckDuckGo
  - 原因：搜索结果是 JS 动态插入的，Python urllib 只能拿到空壳 HTML
  - 症状：直接 curl/urllib 得到的 HTML 里没有搜索结果，只有 JS 脚本
- **需要登录的页面**（36kr、zhihu 等）
- **单页应用（SPA）**：整个页面由 JS 构建

## 验证方法

在动手之前，先测试：

```bash
# 测试1：Python 直接抓取（静态页面）
curl -s https://目标url | grep -c "要的数据" > 0 则可用

# 测试2：带代理测试
python3 -c "
import urllib.request
proxy = urllib.request.ProxyHandler({'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'})
opener = urllib.request.build_opener(proxy)
resp = opener.open('https://目标url', timeout=15)
html = resp.read().decode('utf-8', errors='ignore')
print(f'Got {len(html)} bytes')
"
```

## 已知陷阱

### Bing/Google 中文搜索污染
- Bing 国内版（cn.bing.com）搜索中文关键词时，结果被城市/地名信息干扰
- 例：搜索"上海数据交易所"返回上海市政府、旅游景点，而非数据交易所信息
- 解决：用英文关键词，或用 site: 限定域名，或换用专业财经媒体站内搜索

### Privacy Affairs URL 变更
- 旧 URL `privacyaffairs.com/dark-web-price-index-2024/` → 返回 404
- 新 URL 未知，需要重新搜索找到正确地址

### 代理配置
- 本机代理端口：7890（HTTP: http://127.0.0.1:7890）
- Python 设置：`urllib.request.ProxyHandler({'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'})`

## 工作流选择

| 场景 | 工具选择 |
|------|---------|
| 静态新闻/数据页面 | Python urllib（走代理） |
| 搜索引擎结果 | browser_navigate + browser_snapshot |
| 需要 JS 执行后才能看到内容 | browser 工具 |
| 登录墙后的内容 | browser（配合人工登录） |
| 大规模自动化搜索 | delegate_task 并行 browser_navigate |

## 架构建议

对于需要"自动搜索+提取"的工具：
- **控制层**：Python（调度任务、解析、生成报告）
- **执行层**：Hermes browser 工具（执行 JS 渲染的搜索）
- 不要试图用 Python 模拟浏览器（Selenium/playwright 复杂度高，不如直接用 browser 工具）

## 验证步骤
任何网页抓取任务：
1. 先 curl/Python 直接抓 → 看是否有内容
2. 无内容 → 切 browser 工具
3. browser 工具超时 → 检查 URL 是否正确、目标站点是否可访问
