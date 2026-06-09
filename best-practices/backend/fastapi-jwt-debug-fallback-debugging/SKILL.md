---
name: fastapi-jwt-debug-fallback-debugging
description: FastAPI DEBUG 模式下 JWT 验证失败 fallback 到 dev_user 导致角色权限检查失效的调试方法论
category: backend
tags: [debugging, api, python, fastapi, jwt, authentication, permission, debug-mode]
version: 1.0.0
author: Hermes Agent
license: MIT
---

# FastAPI JWT DEBUG Fallback 调试方法论

## 触发条件

- 修改了 `require_role` 或 `get_current_user` 装饰器
- 用 viewer/operator 角色的 token 测试权限接口，仍然返回 200（而非期望的 403）
- 代码中明确添加了 `require_role("admin", "operator")` 但不生效

## 核心问题：DEBUG 模式下的 auth fallback

```
生产模式：JWT 失效 → 401 Unauthorized
DEBUG 模式：JWT 失效 → fallback 到 dev_user (role=admin) → 200 OK
```

FastAPI 应用中通常有类似这样的中间件或依赖：

```python
# api/dependencies.py 或中间件
async def get_current_user(...):
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        user_role = payload.get("role")
        user_id = payload.get("sub")
    except JWTError:
        if settings.DEBUG:
            # DEBUG 模式：验证失败则用 dev_user bypass
            return DevUser(id=999, role="admin", username="dev_user")
        else:
            raise HTTPException(status_code=401, detail="Invalid token")
```

**后果**：即使你正确添加了 `require_role("admin", "operator")`，DEBUG 模式下 viewer 的 token 验证失败后会 fallback 到 admin 角色，权限检查全部通过。

## 验证方法

**不要相信 DEBUG 环境下的 200**。必须用以下方式验证：

### 方法 1：临时关闭 DEBUG（推荐用于验证）

```python
# 修改 settings
DEBUG = False  # 或
# 环境变量
export DEBUG=false
```

重启服务后测试：
```bash
VIEWER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"viewer_user","password":"Viewer@123456"}' | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  "http://localhost:8000/api/v1/workorders/export?format=csv"
# 期望：403
```

### 方法 2：查看日志中的认证路径

```bash
docker logs itops-api --since 1m | grep -E "get_current_user|fallback|dev_user|DEBUG"
```

### 方法 3：直接 curl 不带 Authorization header

```bash
curl -s -o /dev/null -w "%{http_code}" \
  "http://localhost:8000/api/v1/workorders/export?format=csv"
# DEBUG 模式：200（fallback dev_user）
# 生产模式：401
```

## 实际案例

ITOps Platform `workorder.py` 的 `/export` 端点添加了 `require_role("admin", "operator")`：

```python
@router.get("/export")
@require_role("admin", "operator")  # 添加了权限限制
async def export_workorders(...):
    ...
```

测试结果：
- viewer token 在 DEBUG 模式下 → 200（因为 JWT 解码失败 fallback 到 dev_user）
- viewer token 在生产模式下 → 403 `{"detail":"Role required: admin,operator"}`

## 修复验证流程

```
Step 1: 临时设置 DEBUG=False，重启服务
Step 2: 用 viewer token 调用受限接口 → 期望 403
Step 3: 用 admin token 调用受限接口 → 期望 200
Step 4: 恢复 DEBUG=True（如果需要）
```

## Pitfalls

- 不要在 DEBUG 环境下验证权限修复是否生效——永远先关掉 DEBUG
- 即使 API 返回了正确的 403，也要确认是"真正的权限拒绝"而非"JWT 解析失败"
- `curl` 不带 token 的响应可以帮助判断是 fallback 还是真正的权限检查
