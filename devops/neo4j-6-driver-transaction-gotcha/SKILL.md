---
name: neo4j-6-driver-transaction-gotcha
description: Neo4j Python Driver 6.x 写操作不生效（事务未提交）的诊断与修复
tags: ["neo4j", "python", "driver", "transaction", "6.x"]
category: devops
---

# Neo4j Python Driver 6.x 事务提交要点

## 核心问题
Neo4j Python Driver 6.x 中，`session.run()` 在 `with session()` 上下文管理器内**不会自动提交事务**。节点/关系创建会静默回滚，不报错，不抛异常，但 Neo4j 里根本找不到数据。

## 症状
- `create_node()` 返回成功（生成了 UUID node_id）
- Neo4j HTTP API 查询 `MATCH (n) RETURN count(*)` 始终为 0
- `Neo4jDriver` 所有写操作看起来正常，但数据全部丢失

## 根因
Neo4j 6.x 区分**auto-commit transactions**（`session.run()`）和**explicit transactions**（`session.execute_write()` / `session.begin_transaction()`）。
- `session.run()` 是 auto-commit，但 auto-commit 在某些上下文（如 `with session()` 块）中行为不同
- 正确做法：对写操作使用 `session.execute_write()`

## 修复模版
```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

# ✅ 正确：写操作用 execute_write
with driver.session() as session:
    def _create_node(tx):
        result = tx.run("CREATE (n:Label $props) RETURN n", props={"name": "test"})
        result.consume()  # consume 才会提交
    session.execute_write(_create_node)

# ✅ 正确：execute_write 直接传 lambda
with driver.session() as session:
    session.execute_write(lambda tx: tx.run("CREATE (n:Test)").consume())

# ✅ 读操作可以用 session.run（自动提交）
with driver.session() as session:
    result = session.run("MATCH (n) RETURN n LIMIT 10")
    for record in result:
        print(dict(record["n"]))

# ❌ 错误：直接 session.run() 写操作不生效
with driver.session() as session:
    session.run("CREATE (n:Bad {x:1})")  # 不会报错，但不会写入！
```

## 补充：本 session 发现的新坑

### 坑 1：`result.single()` 必须在 tx 函数内调用
`result.single()` 是状态消耗型（consumes the result），且必须在 `execute_write` 的 tx lambda 内部调用。事务关闭后调用会返回 None：
```python
# ✅ 正确：single() 在 tx 内
def create_relationship_tx(tx, ...):
    result = tx.run("MATCH (a), (b) WHERE ... CREATE (a)-[r]->(b) RETURN r")
    record = result.single()        # 在 tx 内调用
    result.consume()                # 提交
    return record

record = session.execute_write(create_relationship_tx, ...)

# ❌ 错误：事务结束后才 single()
result = session.execute_write(lambda tx: tx.run("CREATE ... RETURN r"))
record = result.single()  # None！事务已关闭
```

### 坑 2：`stats()` 等只读操作如果跟在写操作后面，必须新开 session
```python
# ❌ 错误：同 session 先写后读，读不到刚写的
with driver.session() as session:
    session.execute_write(lambda tx: tx.run("CREATE (n:Test)").consume())
    result = session.run("MATCH (n) RETURN count(*)")  # 可能返回 0

# ✅ 正确：stats 等只读用独立 session
def stats(self):
    with self.driver.session() as session:
        node_count = session.run("MATCH (n) RETURN count(*)").single()["count(*)"]
    with self.driver.session() as session:  # 新 session
        rel_count = session.run("MATCH ()-[r]->() RETURN count(r)").single()["count(r)"]
    return {"nodes": node_count, "relationships": rel_count}
```

### 坑 3：多个 uvicorn 进程同时运行导致 Neo4j 状态不一致
同一端口 8000 上有多个 uvicorn 进程时，服务进程 A 写入的数据对服务进程 B 不可见（driver 实例隔离）。表现为：API 返回 21 节点，但直接 Python 脚本查 Neo4j 为 0。
**诊断**：`ps aux | grep uvicorn`，kill 所有旧进程，只保留一个。

### 坑 4：`result.consume()` 才能提交事务
`result.consume()` 的作用不仅是丢弃结果集，**它才是真正触发事务提交的调用**：
```python
session.execute_write(lambda tx: tx.run("CREATE (n:Test)").consume())  # ✅
session.execute_write(lambda tx: tx.run("CREATE (n:Test)"))             # ❌ 不提交
```

### 坑 5：`StringEnum` TypeDecorator 从 DB 读出的是原始字符串
`str(case.fault_level)` 可以，`.value` 会报错 `'str' object has no attribute 'value'`：
```python
# ❌ 错误：MySQL ENUM/StringEnum 读出来是 str，不是 enum 对象
severity = alert.level.value

# ✅ 正确
severity = str(alert.level)
```

## 验证方法
写完节点后，立即用 neo4j HTTP API 或 Python 驱动**重新开一个 session**查询确认数据存在：
```python
from neo4j import GraphDatabase
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
with driver.session() as s:
    count = s.run("MATCH (n:Label) RETURN count(*) as cnt").single()["cnt"]
    print(f"Persisted: {count} nodes")
```

## Neo4j HTTP API 验证（用于对比）
```bash
curl -u neo4j:password -H "Content-Type: application/json" \
  http://localhost:7474/db/neo4j/tx/commit \
  -d '{"statements":[{"statement":"MATCH (n) RETURN count(*)"}]}'
```
注意：HTTP API 本身是 auto-commit 的，没有这个问题。

## 适用版本
- Neo4j Python Driver 6.x（已知 6.2.0）
- Neo4j 5.x 服务器（已知 5.25.1, 5.26.26）
