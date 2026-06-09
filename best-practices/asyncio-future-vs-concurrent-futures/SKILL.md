---
name: asyncio-future-vs-concurrent-futures
description: asyncio.Future.result() 不接受 timeout 参数，loop.run_in_executor() 返回 asyncio.Future 而非 concurrent.futures.Future 的陷阱
category: best-practices
tags: [python, asyncio, concurrent-futures, threading, fastapi, timeout, executor]
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    related_skills: [systematic-debugging, streaming-protocol-debugging, asyncio-tcp-check-debugging]
---

# asyncio.Future vs concurrent.futures.Future — timeout 参数陷阱

## 核心问题

在 FastAPI/uvicorn 环境中，想给异步上下文中的 LLM 调用加超时，常见的写法会触发 `TypeError: Future.result() takes no arguments`：

```python
# ❌ 错误写法
loop = asyncio.get_event_loop()
future = loop.run_in_executor(None, sync_callable, arg)
result = future.result(timeout=60)  # TypeError: takes no arguments
```

**原因**：`run_in_executor()` 返回的是 `asyncio.Future`，不是 `concurrent.futures.Future`。`asyncio.Future.result()` 不接受任何参数。

## 正确的超时做法

### 方案 1：ThreadPoolExecutor.submit()（推荐）

```python
import concurrent.futures

executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

def sync_callable(arg):
    # 同步操作，如 LLM HTTP 调用
    return llm_client.chat(prompt)

future = executor.submit(sync_callable, arg)
try:
    result = future.result(timeout=60)  # ✅ concurrent.futures.Future 支持 timeout
except concurrent.futures.TimeoutError:
    logger.warning("LLM call timed out after 60s")
    result = None
```

### 方案 2：模块级缓存的 SyncLLMClient

在 uvicorn 启动的 event loop 中，避免在请求处理函数内创建新的 event loop。正确做法是模块级单例缓存：

```python
# ❌ 在请求内创建新 loop — 与 uvicorn 已有 loop 冲突
async def endpoint():
    loop = asyncio.new_event_loop()  # RuntimeError: loop already running
    client = SyncLLMClient(loop=loop)

# ✅ 模块级单例缓存 — 复用启动时创建的 loop
_sync_client = None

def _get_sync_client():
    global _sync_client
    if _sync_client is None:
        _sync_client = SyncLLMClient()
    return _sync_client
```

### 方案 3：asyncio.wait_for（仅限 async 函数）

```python
# ✅ 在 async 函数内加超时
async def call_llm_async(prompt):
    result = await asyncio.wait_for(
        async_llm_client.achat(prompt),
        timeout=60.0
    )
    return result
```

## 两类 Future 的关键区别

| 特性 | `asyncio.Future` | `concurrent.futures.Future` |
|------|------------------|----------------------------|
| `result(timeout=N)` | ❌ 不接受参数 | ✅ 支持 `timeout=N` |
| `result()` | 阻塞直到完成 | 阻塞直到完成 |
| `add_done_callback()` | ✅ | ✅ |
| `cancel()` | ✅ | ✅ |
| 由谁创建 | `asyncio` 事件循环 | `ThreadPoolExecutor.submit()` / `ProcessPoolExecutor.submit()` |
| 在 async 中 await | ✅ 直接 await | ❌ 需要 `asyncio.wrap_future()` |

## 诊断方法

```python
import asyncio, concurrent.futures

print(type(asyncio.Future()))  # <class '_asyncio.Future'>
print(type(concurrent.futures.Future()))  # <class 'concurrent.futures.Future'>
print(asyncio.Future().result.__doc__)  # Takes no arguments
print(concurrent.futures.Future().result.__doc__)  # Supports timeout
```

## 触发场景

1. **FastAPI endpoint 中用 `loop.run_in_executor()` 后想加超时** — `run_in_executor` 返回 `asyncio.Future`，无法 `.result(timeout=N)`
2. **uvicorn 环境创建新的 event loop** — `asyncio.new_event_loop()` 与 uvicorn 已有 loop 冲突
3. **混用 async 和同步线程池** — 在 async 函数内调用 `ThreadPoolExecutor.submit().result()` 不会报错，但没有超时保护

## 验证命令

```bash
# 确认 asyncio.Future 不接受 timeout
python3 -c "
import asyncio
f = asyncio.Future()
try:
    f.result(timeout=5)
except TypeError as e:
    print('CONFIRMED: asyncio.Future.result()不接受timeout参数:', e)

# 确认 concurrent.futures.Future 接受 timeout
import concurrent.futures
f2 = concurrent.futures.Future()
f2.result(timeout=5)  # 不报错（会一直阻塞直到有结果）
print('OK: concurrent.futures.Future.result(timeout=N) 接受参数')
"
```

## 相关陷阱

- **httpx Timeout API 变化**：httpx 0.28+ `Timeout(default=...)` 命名参数废弃，需用位置参数
- **嵌套 async def**：Python 3.13+ 嵌套 `async def` 的 scope 行为改变，流式生成器需用模块级函数
- **Session scope**：SQLAlchemy `session_scope()` 返回 `GeneratorContextManager`，必须用 `with` 语句
