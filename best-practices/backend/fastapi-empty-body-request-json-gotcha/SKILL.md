---
name: fastapi-empty-body-request-json-gotcha
description: FastAPI await request.json() 空body时抛出StopIteration的诊断与修复
tags: [fastapi, python, debugging]
---

# FastAPI: `await request.json()` 空 Body 时崩溃

## 问题现象

路由函数中使用：
```python
async def my_endpoint(request: Request):
    body = await request.json()  # ❌ 空body时抛出StopIteration
    req = MySchema(**body)
```

当客户端发送 `POST /api/v1/configs/2/rollback` 带空 body `{}` 时，API 返回 **500**。

## 根因

`request.json()` 底层调用 `json.loads(await request.body())`。当 body 为 `{}` 或 `""` 时：
- `json.loads("{}")` → 正常返回 `{}`
- `json.loads("")` → 抛出 `JSONDecodeError`
- 但在某些 Starlette 版本中，空 body 导致 `StopIteration`（迭代器耗尽）

## 诊断方法

```bash
# 查看真实错误（不在API响应里）
tail -f /tmp/uvicorn.log | grep -i "stopiteration\|json"

# 或者加日志
except Exception as exc:
    logger.error(f"empty body crash: {exc}")
```

错误信息：`StopIteration: ` 或 `JSONDecodeError: Expecting value`

## 修复方案

### 方案A（推荐）：try/except 包裹 + 默认值
```python
async def my_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    req = MySchema(**body)
```

### 方案B：FastAPI 原生 Body 参数（正确方式）
```python
from pydantic import BaseModel
from fastapi import Body

class MyRequest(BaseModel):
    target_version: Optional[int] = None

async def my_endpoint(body: MyRequest = Body(default=MyRequest())):
    version = body.target_version
```

### 方案C：手动解析 + 默认值
```python
async def my_endpoint(request: Request):
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    req = MySchema(**body)
```

## 已发现的问题文件（itops_platform）

| 文件 | 端点数 | 状态 |
|------|--------|------|
| `app/domains/config/router.py` | 2 | ✅ 已修复（try/except） |
| `app/domains/config/service.py` | 1 | ✅ 已修复（第二层防护） |
| `app/domains/strategy/router.py` | 13 | ✅ 已修复（safe_json_body） |
| `app/domains/automation/router.py` | 3 | ✅ 已修复（完全重写） |

## ⚠️ `replace_all` 递归陷阱（关键教训）

使用 patch tool 的 `replace_all` 批量替换 `await request.json()` 时，**会同时替换辅助函数内部的调用**，导致无限递归：

```python
# ❌ 错误：replace_all 把下面函数的内部调用也替换了
async def safe_json_body(request: Request):
    return await safe_json_body(request)  # 无限递归！

# ✅ 正确：内部用不同名称，replace_all 不会命中
async def json_body(request: Request):
    try:
        return await request.json()
    except Exception:
        return {}

# 对外暴露 safe_json_body，路由处理器中 replace_all 只会替换这一层
```

**教训**：使用 `replace_all` 替换函数调用时，辅助函数内部必须用不同名称的内部函数。

## safe_json_body 正确实现模板

```python
from starlette.requests import Request

# 内部函数（不会被 replace_all 命中）
async def json_body(request: Request):
    try:
        return await request.json()
    except Exception:
        return {}

# 对外暴露（路由处理器中调用这个）
async def safe_json_body(request: Request):
    return await json_body(request)
```

然后对每个路由处理器中的 `await request.json()` 做 `replace_all`，只会替换路由层的调用，不会递归到内部。

## 关键教训

1. **永远不要直接用 `await request.json()`** — 必须用 try/except 包裹
2. **FastAPI 原生 `Body` 参数最安全** — Pydantic 自动处理默认值和验证
3. **警惕所有 `except Exception`** — 如果同时打印 `str(exc)` 到响应，会暴露内部细节（安全隐患）
4. **空 body `{}` 不等于无 body** — 只有真正的空 body（Content-Length: 0）才会触发此问题
5. **`replace_all` 有作用域陷阱** — 批量替换函数调用时，辅助函数内部要用不同名称避免递归
