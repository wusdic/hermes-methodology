---
name: python-platform-stdlib-naming-conflict
description: 项目目录名 platform/ 会劫持 Python 标准库 platform 模块，导致 uuid 等内置模块调用 platform.system() 时 AttributeError
tags: [python, import, stdlib, naming, bug]
date_created: 2026-06-04
---

# Python stdlib `platform` Module Naming Conflict

## Symptom
When the current working directory contains a subdirectory named `platform/` and you run code that imports stdlib modules depending on `platform.system()` (e.g., `uuid`, `tempfile`, `pathlib`), you get:

```
AttributeError: module 'platform' has no attribute 'system'
```

## Root Cause
Python's import system resolves `import platform` to `./platform/` (the local directory) before checking `sys.path`, because the current working directory is prepended to `sys.path[0]`. The local `platform/` directory has no `system()` function, causing the AttributeError.

## Example Stack Trace
```
File "/usr/lib/python3.12/uuid.py", line 60, in <module>
    _platform_system = platform.system()
                       ^^^^^^^^^^^^^^^
AttributeError: module 'platform' has no attribute 'system'
```

Triggered by any code that uses `uuid.uuid4()` or similar stdlib utilities when cwd contains `platform/`.

## Solution
Rename the project directory from `platform/` to something that doesn't conflict with stdlib:
```bash
mv platform/ platform_core/
```

Also update any internal imports/paths that reference the old name.

## Prevention
Avoid naming project directories after Python stdlib modules: `platform/`, `signal/`, `socket/`, `test/`, `types/`, `typing/`, `uuid/`, etc.
