---
name: sqlalchemy-session-scope-debugging
description: SQLAlchemy DatabaseManager session_scope 使用误区——@contextmanager 返回 GeneratorContextManager，必须用 with 语句
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [sqlalchemy, python, database, fastapi, context-manager]
    related_skills: [fastapi-503-swallowed-exception-debugging, api-error-translation-debugging]
---

# SQLAlchemy DatabaseManager session_scope Debugging

## Problem
`_db_manager.session_scope()` is a `@contextmanager` decorated generator. It returns a context manager object (generator), NOT a Session. Code that does:

```python
session = self._db_manager.session_scope()
session.query(...)  # AttributeError: '_GeneratorContextManager' object has no attribute 'query'
```

## Root Cause
`@contextmanager` from `contextlib` wraps a generator. When you call `session_scope()` without `with`, you get the generator itself. The actual `Session` only exists inside the `with` block after `yield`.

## Fix
Always use `with` statement:

```python
with self._db_manager.session_scope() as session:
    user = session.query(SystemUser).filter_by(username=username).first()
    # ... use session ...
# session automatically closed/exitted via __exit__
```

## Error Patterns
- `AttributeError: '_GeneratorContextManager' object has no attribute 'query'` → missing `with`
- `AttributeError: '_GeneratorContextManager' object has no attribute 'close'` → context manager used where session expected

## Startup Initialization Order Issue (ITOps Platform specific)
When `_user_store = DBUserStore()` is evaluated at module import time, `__init__` calls `_ensure_default_users()` which queries DB immediately. If `SystemUser` table doesn't exist yet → `ProgrammingError`.

```
uvicorn api.main:app
  → imports api.routes.auth
    → _user_store = DBUserStore()    ← queries DB immediately
      → _ensure_default_users()       ← table may not exist yet
```

`init_db()` only sets up connection, does NOT create tables. `create_all()` is only called in `api/start.py`, NOT in `uvicorn api.main:app` path.

**Critical**: After adding a new model, must:
1. Import it in `modules/foundation/db_models/__init__.py` (otherwise `Base.metadata` doesn't know about it)
2. Manually call `_db_manager.create_all()` to create new tables

## Verification Steps
```python
from modules.foundation.db_models.base import _db_manager
_db_manager.setup()
_db_manager.create_all()
from sqlalchemy import inspect
insp = inspect(_db_manager.get_engine())
print('Tables:', insp.get_table_names())
```

## Signals
- `sqlalchemy.exc.ProgrammingError: Table '...' doesn't exist'` → table not created, check `__init__.py` imports
