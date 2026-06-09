---
name: mysql-enum-uppercase-debugging
description: MySQL ENUM uppercase vs Python lowercase mismatch causing 500 errors — detection, root causes, and fix patterns for itops_platform
---

# MySQL ENUM Uppercase vs Python Lowercase — Debugging Skill

## Problem
MySQL ENUM columns store UPPERCASE values (e.g., `'SERVER_LINUX'`, `'ONLINE'`), but Python enums define lowercase values (e.g., `DeviceType.SERVER_LINUX` → `'server_linux'`). This mismatch causes:
- **Write path**: `DataError: Data truncated` — code passes `'server'` to a column expecting `'SERVER_LINUX'`
- **Read path**: `AttributeError: 'str' object has no attribute 'value'` — code tries to call `.value` on an already-resolved string
- **Write-to-DB path**: `str(enum)` returns `'ClassName.VALUE'` (e.g., `'DeviceStatus.OFFLINE'`) instead of the value

## Detection Method
**Always test with direct Python + real DB driver**, not curl. The API may fail in ways that hide the real cause:

```python
import sys
sys.path.insert(0, '/home/zcxx/.hermes/projects/itops_platform')
from modules.collection.device_manager import _map_device_type, _map_device_status, DBDeviceType, DBDeviceStatus
print(_map_device_type('server').value)      # should be 'SERVER_LINUX'
print(_map_device_status('online').value)     # should be 'ONLINE'
print(str(DBDeviceStatus.OFFLINE))           # WRONG: 'DeviceStatus.OFFLINE'
print(DBDeviceStatus.OFFLINE.value.upper())  # CORRECT: 'OFFLINE'
```

## Fix Patterns

### Pattern 1: Write to MySQL ENUM column
```python
# WRONG — passes lowercase string directly
db_value = str(DeviceTypeEnum.SERVER_LINUX)       # 'DeviceType.SERVER_LINUX'
db_value = device.device_type                      # 'server'

# CORRECT — use mapper + .value.upper()
db_value = _map_device_type(device.device_type).value.upper()  # 'SERVER_LINUX'
db_value = _map_device_status(device.status).value.upper()     # 'ONLINE'
```

### Pattern 2: Write status via CollectionStatus enum
```python
# WRONG
db_status = str(CollectionStatus.OFFLINE)   # 'CollectionStatus.OFFLINE'

# CORRECT — use .value.upper()
db_status = str(CollectionStatus.OFFLINE.value).upper()  # 'OFFLINE'
```

### Pattern 3: Read from DB and return to API (DB uppercase → API lowercase)
```python
def _to_api_device_type(val) -> str:
    """Convert DB uppercase ENUM to API lowercase string."""
    if val is None:
        return 'server'
    s = str(val).upper()
    mapping = {
        'SERVER_LINUX': 'server',
        'SERVER_WINDOWS': 'server_windows',
        'NETWORK_SWITCH': 'network_switch',
        'NETWORK_ROUTER': 'network_router',
        'STORAGE_NAS': 'storage_nas',
        'CLOUD_VM': 'cloud_vm',
        'IOT_DEVICE': 'iot_device',
    }
    return mapping.get(s, 'server')

def _to_api_status(val) -> str:
    """Convert DB uppercase ENUM to API lowercase string."""
    if val is None:
        return 'offline'
    s = str(val).upper()
    mapping = {
        'ONLINE': 'online',
        'OFFLINE': 'offline',
        'WARNING': 'warning',
        'CRITICAL': 'critical',
        'MAINTENANCE': 'maintenance',
        'DECOMMISSIONED': 'decommissioned',
    }
    return mapping.get(s, 'offline')
```

## Known ENUM Columns in itops_platform

### devices table
- `device_type`: `ENUM('SERVER_LINUX','SERVER_WINDOWS','NETWORK_SWITCH',...)` — UPPERCASE
- `status`: `ENUM('ONLINE','OFFLINE','WARNING','CRITICAL','MAINTENANCE','UNKNOWN')` — UPPERCASE

### kb_sop_documents table
- `status`: `ENUM('DRAFT','PUBLISHED','ARCHIVED')` — uppercase; handled by `StringEnum` TypeDecorator

### fault_cases table
- `fault_level`: `ENUM('INFO','WARNING','ERROR','CRITICAL')` — uppercase; handled by `StringEnum` TypeDecorator
- `fault_status`: `ENUM('OPEN','INVESTIGATING','RESOLVED','CLOSED')` — uppercase; handled by `StringEnum` TypeDecorator

## Key Files
- `api/routes/asset.py` — `_map_device_type/.value.upper()` on write, `_to_api_*` on read
- `modules/collection/device_manager.py` — `str(db_status.value).upper()` on write
- `modules/business/knowledge_base/models.py` — `StringEnum` TypeDecorator for knowledge base enums

## Verification
After fixing, restart service and test both paths:
```python
# Write: create a device with device_type='server'
import requests
r = requests.post('http://localhost:8000/api/v1/assets/device', json={...})
# Read back: should return device_type='server', not 'SERVER_LINUX' or error
r = requests.get('http://localhost:8000/api/v1/assets/device/<id>')
assert r.json()['device_type'] == 'server'
```
