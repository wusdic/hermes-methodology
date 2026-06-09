---
name: sqlalchemy-nested-session-gotcha
description: SQLAlchemy session scope gotcha — get_db_session() 作为 context manager 时不能嵌套调用，导致 TransactionError
category: backend
tags: [debugging, sqlalchemy, python, fastapi, session, transaction, itops-platform]
version: 1.0.0
author: Hermes Agent
license: MIT
---

# SQLAlchemy Session Scope Gotcha: 嵌套 get_db_session() 导致 TransactionError

## 触发条件

- Service A 方法在 `with get_db_session() as db:` 内部
- Service A 调用了另一个 `@staticmethod` Service B 的方法
- Service B 方法内部也使用了 `with get_db_session() as db:`
- 结果：`ImportError: cannot import name 'engine'`，或 `TransactionError`

## 症状

```python
# ❌ 错误：rollback_version 在自己的 session 里调用 create_version
# create_version 内部也有 with get_db_session() → 嵌套 session 冲突
class PolicyService:
    def rollback_version(version_id: str):
        with get_db_session() as db:  # ← 外层 session
            ...
            new_version_id = PolicyService.create_version(...)  # ← create_version 内部也有 with get_db_session()！
            # 报错：ImportError 或 TransactionError
```

## 根因

`get_db_session()` 是上下文管理器（`@contextmanager`），在 SQLAlchemy 中每个 session 绑定到同一个线程/协程的特定事务。嵌套调用时：

- 内层 `get_db_session()` 尝试开启新 session
- 新 session 试图参与已存在的事务
- 或者内层 session 被错误地当成外层的子事务

## 修复方法

**将所有操作放在同一个 session 内，内联逻辑而不是调用其他 service 方法**：

```python
@staticmethod
def rollback_version(version_id: str):
    with get_db_session() as db:
        from app.domains.policy.models import Policy, PolicyVersion

        version_record = db.query(PolicyVersion).filter(
            PolicyVersion.version_id == version_id
        ).first()
        ...
        # 不要再调用 create_version()！
        # 直接在这里创建新版本对象：
        new_version_id = f"pv-{uuid.uuid4().hex[:16]}"
        new_pv = PolicyVersion(
            version_id=new_version_id,
            policy_id=policy.policy_id,
            version=next_version,
            content_snapshot=json.dumps(PolicyService._policy_to_dict(policy)),
            change_summary=f"回滚到版本 {version_record.version}",
            created_by="system",
            is_active=False,
        )
        db.add(new_pv)
        db.commit()
        return new_version_id
```

## 规则

> **在 ITOps Platform 中，如果一个 service 方法已经使用了 `with get_db_session() as db:`，不要再从其内部调用另一个同样使用 `with get_db_session() as db:` 的 service 方法。**
>
> 正确做法：把被调用者的逻辑直接内联到调用者内部，或将两者的逻辑合并到同一个事务中。

## 验证

```bash
python3 -c "
from modules.foundation.db_models.base import DatabaseManager
db_mgr = DatabaseManager()
db_mgr.setup()
from modules.foundation.db_models.base import Base
Base.metadata.create_all(bind=db_mgr.get_engine())
print('OK')
"
```
