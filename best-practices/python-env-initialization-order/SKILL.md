---
name: python-env-initialization-order
description: Python .env 加载时机与模块级单例初始化顺序——FastAPI 框架下 DatabaseManager 等单例在 import 时就已初始化，早于 API startup，导致 .env 未被加载
---

# Python .env 加载时机与模块级单例初始化顺序

## 触发条件
使用 FastAPI/Uvicorn 框架 + SQLAlchemy 单例 + `python-dotenv` 或手动 `.env` 加载，数据库连接报 `Access denied for user 'root'@'localhost'`（明明配置了非 root 账号）。

## 根因
API 入口（如 `api/main.py` 的 `@app.on_event("startup")` 或 `api/start.py`）在 startup 时才加载 `.env`，但 `DatabaseManager`、`Redis` 等模块在 **import 时**就已经执行了模块级代码（如 `engine = create_engine(...)`）。此时 `os.environ` 尚未填充，导致使用默认值（如 `localhost` 的 root 账号）。

## 诊断流程
1. 日志出现 `OperationalError: Access denied for user 'root'@'localhost'`
2. 确认 `.env` 里配置的 DB 用户是 itops/其他非 root 账号
3. 确认 API 代码有 `load_dotenv()` 或自定义 `.env` 加载
4. 确认仍有报错 → 检查报错模块是否在 API startup **之前**就被 import 了

## 正确做法
在**报错模块自身**的顶层加载 `.env`，而不是依赖 API 入口。

### 修复模板（以 SQLAlchemy 单例为例）

```python
# modules/foundation/db_models/base.py

import os

# ★★★ 必须放在 import 之后、任何模块级代码之前 ★★★
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_dotenv_path = os.path.join(_project_root, ".env")
if os.path.exists(_dotenv_path):
    with open(_dotenv_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# 之后才是 SQLAlchemy 代码
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

class DatabaseManager:
    _instance = None
    def __init__(self):
        # create_engine() 在这里执行，此时 os.environ 已经填充了 .env 的值
        db_url = os.getenv("DB_URL")  # 或 ITOPS_DB_HOST/ITOPS_DB_PASSWORD 等
        self.engine = create_engine(db_url, ...)
```

## 关键原则
1. **`.env` 加载必须放在被依赖模块的模块级顶层**，不能放在 API 入口
2. 使用 `os.environ.setdefault()` 而不是 `os.environ[""] = `，避免覆盖已存在的环境变量
3. 路径计算用 `__file__` + `os.path.dirname()` 向上查找项目根目录，比硬编码绝对路径更健壮

## 验证方法
重启 API 后，采集器/数据库连接不再出现 root@localhost 报错。
