---
name: fastapi-405-path-discovery
description: When FastAPI returns 405 Method Not Allowed — discover the actual registered route paths via OpenAPI spec and Pydantic model inspection
category: best-practices
tags: [fastapi, debugging, openapi, 405, route-discovery]
version: 2026-05-30
---

# FastAPI 405 路径发现方法论

## 问题
调用 `POST /api/v1/aiops/root-cause` 返回 405 "Method Not Allowed"，但 TODO.md 或文档说这个接口存在。

## 诊断流程

### Step 1: 查询 OpenAPI spec（最快）
```bash
# 查看所有注册的路径
curl -s http://localhost:8000/openapi.json | python3 -c "
import sys, json
paths = json.load(sys.stdin).get('paths', {})
for p, methods in sorted(paths.items()):
    for m in methods.keys():
        if m in ('get','post','put','delete'):
            print(f'{m.upper():6} {p}')
" | grep -i root-cause
```

### Step 2: 检查具体路径的 HTTP 方法
```bash
curl -s http://localhost:8000/openapi.json | python3 -c "
import sys, json
paths = json.load(sys.stdin)['paths']
target = '/ai/analyze/{alert_id}/root-cause'
if target in paths:
    print(target, list(paths[target].keys()))
"
```

### Step 3: 检查 Request Model 字段
```bash
# 422 的 loc 信息告诉你是哪个字段缺失
curl -s -X POST http://localhost:8000/api/v1/ai/analyze/1/root-cause \
  -H 'Authorization: Bearer ...' -H 'Content-Type: application/json' -d '{}'
# 返回 422: [{'loc': ['body', 'include_llm'], ...}]
```

### Step 4: grep 路由定义
```bash
grep -n "root-cause\|RootCause\|analyze.*alert" api/routes/ai.py | head -20
```

## ITOps Platform 常见路径问题

| 错误路径（文档） | 正确路径 | 问题 |
|---|---|---|
| POST /aiops/root-cause | POST /ai/analyze/{alert_id}/root-cause | 前缀是 /ai 不是 /aiops |
| POST /workorders/{id}/generate-knowledge | POST /workorders/tickets/{workorder_id}/generate-knowledge | 中间多了 /tickets |
| GET /notifications/history | GET /notifications/messages | 路径名错误 |
| GET /knowledge/articles/{id} | GET /knowledge/sop/{doc_id} | knowledge 有两套路由，被 stub 覆盖 |

## 关键教训
- **405 = 路径正确但方法错**，或**路径被其他 router 覆盖**
- **422 = 路径和方法正确，但 body 字段缺失或类型错误**
- **OpenAPI spec 是最终真相**——它列出所有实际注册的端点
- FastAPI `include_router` 可以有多个同名路径，**后注册的覆盖先注册的**
