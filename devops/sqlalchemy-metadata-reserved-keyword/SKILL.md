---
name: sqlalchemy-metadata-reserved-keyword
description: Fix SQLAlchemy reserved keyword `metadata` — rename DB column to extra_data
---

# SQLAlchemy metadata Reserved Keyword Fix

## Problem
SQLAlchemy cannot use `metadata` as a model attribute name because it's a reserved keyword on `MetaData`. When defining:

```python
class Asset(Base):
    __tablename__ = 'assets'
    metadata = Column(JSON)  # ❌ AttributeError or silent mapping failure
```

The column either fails to map or causes cryptic errors.

## Solution
**Rename the DB column, not the model.** Use `extra_data` in both SQLAlchemy model and database.

```python
# SQLAlchemy model
class Asset(Base):
    __tablename__ = 'assets'
    extra_data = Column('extra_data', JSON, nullable=True)  # explicit column name

# Database
ALTER TABLE assets CHANGE COLUMN `metadata` `extra_data` JSON DEFAULT NULL;
```

## Why Not Other Approaches?

| Approach | Problem |
|---|---|
| Use `column_property('metadata')` | Still maps to reserved `MetaData` object internally |
| Use `metadata_ = Column('metadata', ...)` | Underscore workaround, ugly |
| Set `metadata = Column('metadata', ...)` with custom mapper | Fragile, breaks on autoflush |

**Rename the DB column is always the right answer** for reserved words like `metadata`, `table`, `index`, `order`, `group`.

## Verification
After ALTER, restart the uvicorn process so SQLAlchemy engine picks up new column names.

```python
from sqlalchemy import inspect
inspector = inspect(engine)
columns = [c['name'] for c in inspector.get_columns('assets')]
assert 'extra_data' in columns
assert 'metadata' not in columns
```

## Project Context
- ITOps Platform: `app/domains/asset/models.py` Asset model
- Migration script: `scripts/migration/013_asset_center.sql`
