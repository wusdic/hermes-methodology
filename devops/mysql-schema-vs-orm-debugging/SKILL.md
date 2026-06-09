---
name: mysql-schema-vs-orm-debugging
description: MySQL Schema vs SQLAlchemy ORM 模型不一致调试 — 500错误根因定位
tags: [mysql, sqlalchemy, debugging, api]
---

# MySQL Schema vs SQLAlchemy ORM 模型不一致调试

## 问题特征

API 返回 500 Internal Server Error，但：
- `except Exception as exc: return {"detail": str(exc)}` 这类中间层吞掉了真实错误
- `curl -I` 只能看到状态码，看不到错误详情
- `tail -f api.log` 没有输出（因为异常被 `except` 捕获）

**典型错误信息**：
```
sqlalchemy.exc.OperationalError: (1054, "Unknown column 'strategies.scope' in 'field list'")
```

## 根因

SQLAlchemy ORM 模型定义了列，但数据库实际表缺少该列（Schema 迁移未执行）。

## 调试方法论

### 第一步：找真实错误日志

```bash
# 方法1：直接找日志文件
tail -f /tmp/itops_data/logs/api.log

# 方法2：uvicorn 重定向到文件（推荐用于调试）
python -m uvicorn api.main:app --log-level info 2>&1 | tee /tmp/uvicorn.log

# 方法3：在 except 块中强制记录
except Exception as exc:
    logger.error(f"REAL ERROR: {type(exc).__name__}: {exc}", exc_info=True)
    raise  # 不要吞掉
```

### 第二步：确认是 schema 问题

错误信息包含：
- `Unknown column 'xxx' in 'field list'` — 列不存在
- `(1045, "Access denied")` — 权限/密码问题
- `(1146, "Table doesn't exist")` — 表不存在

### 第三步：对比 ORM 模型和实际 DB

**找到 ORM 模型**：
```bash
grep -n "scope.*=.*Column" app/domains/strategy/models.py
```

**直接查询数据库**：
```python
import pymysql
conn = pymysql.connect(host='localhost', user='itops_platform', 
                        password='...', database='itops_platform')
cur = conn.cursor()
cur.execute('DESCRIBE strategies')  # MySQL
for col in cur.fetchall():
    print(col)
```

### 第四步：修复

**方案A — 保守修复（让 ORM 适应 DB）**：
从 ORM 模型中删除不存在的列

**方案B — 正确修复（补 DB 列）**：
```sql
ALTER TABLE strategies ADD COLUMN scope JSON AFTER status;
```

## 关键教训

1. **不要依赖 API 错误响应** — 中间件的 `except Exception` 会返回误导性信息
2. **始终查看服务日志** — uvicorn 进程的 stdout/stderr 或配置的日志文件
3. **Schema 漂移是常见问题** — API 代码新增字段但 DB 迁移未执行时发生
4. **pydantic `ValidationError`** 不等于成功 — OpenAPI spec 显示 Query 参数 vs 实际路由用 Body 参数，说明路径可能注册了两次或 schema 解析失败
5. **ORM 可能有比 DB 更多的列（幽灵列）** — 这是本项目最常见的不一致形式：ORM 定义了 20+ 列但 DB 只有 9 列。`SELECT *` 时 SQLAlchemy 会尝试读取不存在的列导致 `Unknown column` 错误。**修复策略：让 ORM 适配 DB（删除幽灵列），而不是反过来改 DB**。
6. **Enum 存储类型必须匹配 DB 列类型** — `SQLEnum(StrategyPriority, native_enum=False)` 将 enum name 存为字符串（如 `"HIGH"`），若 DB 列是 INT 会导致 `DataError` 或查询结果异常。应使用 `.value` 显式取整数。
7. **Service 层传入不存在的模型参数会被 SQLAlchemy 拒绝** — `previous_values`、`operator_ip` 等参数在 service.py 里传入 ORM 构造，但 ORM 模型没有这些列，会报 `TypeError: 'previous_values' is an invalid keyword argument`。搜索整个 service.py 删除所有幽灵参数。
8. **关联关系的 back_populates 会级联失败** — 若一端删除了关系字段，另一端的 `back_populates="xxx"` 会报 `Mapper has no property 'xxx'`。删除 ORM 列时同步删除相关 `relationship` 和 `back_populates`。

## 本项目实战案例（strategy 模块）

**真实 DB schema** (`strategy_versions` 表只有 9 列)：
```
id | strategy_id | version | config | rules | change_summary | change_type | operator | created_at
```

**ORM 模型曾错误引用**（23个幽灵列）：name, description, strategy_type, category, priority, status, scope, conditions, actions, change_type(enum), previous_version_id, previous_values, operator_ip, approved_by, approved_at, strategy(relationship)

**Service 层曾传入的幽灵参数**：previous_values=old_values, operator_ip=operator_ip, change_type=ChangeType.UPDATE(enum)

**根因**：历史代码设计了一个"完整版本快照"但从未执行对应 DB 迁移。

**修复方法**：
1. `ALTER TABLE strategy_versions ADD COLUMN scope JSON, ADD COLUMN tags JSON`（补 DB）
2. 重写 `StrategyVersion` ORM 模型，只保留 9 个真实列
3. 将所有 `change_type=ChangeType.XXX` 改为 `change_type="UPDATE"` 字符串
4. 将版本快照完整 config 序列化为 JSON 存在 `config` 列中（不存单独列）
5. 删除 `Strategy` 模型中的 `versions = relationship(..., back_populates="strategy")`
6. 删除 service.py 中所有 `previous_values=` 和 `operator_ip=` 参数

## 相关文件位置
- API日志：`/tmp/itops_data/logs/api.log`
- uvicorn日志：`/tmp/uvicorn.log`
- ORM模型：`app/domains/{domain}/models.py`
- Schema定义：`app/domains/{domain}/schemas.py`
