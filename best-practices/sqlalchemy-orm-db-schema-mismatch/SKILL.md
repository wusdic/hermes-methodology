---
name: sqlalchemy-orm-db-schema-mismatch
description: SQLAlchemy ORM 模型定义的列与数据库真实列不一致——导致所有查询返回500的根级别bug
tags: [sqlalchemy, python, debugging, fastapi]
related_skills: [fastapi-empty-body-request-json-gotcha]
---

# SQLAlchemy ORM vs 数据库 Schema 不匹配

## 问题现象

某个 domain 的所有 API 端点（CRUD + 版本历史 + 发布）全部返回 **500 Internal Server Error**，但：
- 数据库连接正常
- 表存在
- 直接 SQL 查询正常
- 其他 domain 正常

## 根因

ORM 模型（`models.py`）定义了数据库中**不存在的列**。SQLAlchemy 查询时生成错误的 SELECT 语句，访问不存在的列名导致数据库异常。

## 诊断流程

```bash
# 1. 确认 ORM 模型行数 vs 真实需要
wc -l app/domains/strategy/models.py

# 2. 查看 ORM 定义的列（从 models.py）
grep -n "Column\|relationship" app/domains/strategy/models.py

# 3. 确认数据库真实列（MySQL）
DESCRIBE strategy_versions;

# 4. 生成正确的 create table SQL
SHOW CREATE TABLE strategy_versions\G

# 5. 差异对比
# ORM 有 15+ 列，DB 只有 9 列 —— 找出不匹配的
```

## 典型案例（itops_platform strategy_versions）

| ORM 模型定义 | 数据库真实列 |
|---|---|
| id, strategy_id, version, **name**, **description**, **strategy_type**, **priority**, **created_by**, **scope**, **tags**, config, rules, change_summary, change_type, **operator**, **operator_ip**, **previous_values**, created_at, **updated_at** | id, strategy_id, version, **config(JSON)**, rules, change_summary, change_type, **operator**, created_at |

**差异**：
- ORM 多：name, description, strategy_type, priority, created_by, scope, tags, operator_ip, previous_values, updated_at
- DB 有：config (JSON 存储完整快照)

## 修复原则

**以数据库为真实数据源**，ORM 必须适配 DB，而非修改 DB：
- 删掉所有 DB 不存在的列
- 用 JSON 列（config）存储需要版本化的字段
- 从 config JSON 解析字段给 API 响应

## 修复步骤

1. **重写 ORM 模型** — 只保留 DB 真实列
2. **修改 service 层** — 版本记录改用 JSON config 快照
3. **修改 router 层** — 序列化时从 config JSON 解析字段
4. **删除幽灵 relationship** — `back_populates` 引用了不存在的字段

## 已修复案例

**StrategyVersion** (itops_platform `app/domains/strategy/models.py`):
- 原来：15+ 列，包含 name/description/priority/created_by 等幽灵列
- 修复后：9 列，仅含 DB 真实列，版本化字段存入 config JSON
- 连带修复：service 层 create_strategy 版本记录逻辑、router 层序列化逻辑

**StrategyPriority 枚举**：
- 原来：`str, enum.Enum` 值为 `"high"/"medium"`
- 数据库：INT 列
- 修复：改为纯 `enum.Enum` 值用整数，`service.py` 层映射 `str → int`

## 关键教训

1. **ORM ≠ DB schema** — 每次新增字段时，必须同步确认 DB 列是否存在
2. **幽灵列会导致静默失败** — ORM 不会报错，直到实际查询才会触发
3. **版本化字段用 JSON** — 不确定未来要版本化哪些字段时，用 JSON 列最灵活
4. **先查 DB 再改 ORM** — 不确定列是否存在时，先 `DESCRIBE table_name` 确认
