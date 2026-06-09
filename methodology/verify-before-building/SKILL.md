---
name: methodology/verify-before-building
description: 功能开发前先验证——搜索现有代码+curl API确认不存在再动手，避免重复造轮子
category: methodology
tags: [workflow, debugging, fastapi]
---

# 验证优先原则：先确认不存在，再动手实现

## 问题

新功能被标注为"未实现"，结果花了大量时间实现后，发现后端其实已经完整存在，只是缺少前端入口。

## 流程

### Step 1：搜索关键词
```bash
# 在项目中搜索功能相关关键词
grep -r "rollback\|get_rollback_manager\|RollbackManager" --include="*.py" .

# 搜索 API 端点
grep -r "@router.*rollback\|POST.*rollback\|GET.*rollback" --include="*.py" .
```

### Step 2：curl 实际 API
```bash
# 拿到 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123456"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('token', d.get('access_token','')))")

# 测试 API 是否已存在
curl -s "http://localhost:8000/api/v1/automation/rollback-history" \
  -H "Authorization: Bearer $TOKEN"

# 404 = 不存在，200 = 存在
```

### Step 3：检查数据库表
```sql
-- 检查表是否存在
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'itops_platform' AND table_name LIKE '%rollback%';
```

## 典型场景

| 场景 | 验证命令 |
|---|---|
| 新功能被标注"未实现" | `curl` 实际 API 端点 + `grep` 源码 |
| P2-21 回滚 API | `curl /automation/rollback-history` → 已有 ✅ |
| P2-22 部门管理 | `curl /admin/departments` → 404，需新建 |
| P1-12 备份 API | `curl /admin/backup` → 已有（admin 路由提供）|

## 教训

- GAP_ANALYSIS.md 标注"未实现" ≠ 后端不存在（可能是已有 API 无前端入口）
- "验证命令永远先于实现"——花 1 分钟 curl 验证，省掉 1 小时实现

---

## 补充原则：先验证文档准确性，再处理清单

收到长清单（30+ 项）时，**不要逐项埋头修复**。先做"元验证"：

| 检查项 | 方法 |
|---|---|
| 目录/模块是否真的存在 | `find` + `grep` 搜实际路径 |
| API 接口是否真的 404 | `curl` 实际请求（完整响应，不只看状态码）|
| 已知问题是否历史已修复 | 直接 curl 验证而非默认"肯定坏了" |
| 前提条件是否成立 | 例如"模块重复"需先确认重复的模块真的存在 |

**本次经验**：整体优化要求.docx 标注 30+ 问题，实际超过 2/3 是：
- 前提不成立（如 `services/monitoring` 目录不存在）
- 历史迭代已修复（如 `/admin/dict/init` sort_order 错误已不存在）
- 非阻塞设计问题（如 SECRET_KEY 默认值）

花 2 小时系统验证 + curl 全部接口，结论是"只剩 3 个真实问题"，远低于文档描述。避免了大量无效修复工作。
