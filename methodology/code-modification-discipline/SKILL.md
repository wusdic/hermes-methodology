---
name: code-modification-discipline
category: methodology
description: Verify before reporting problems, confirm before fixing. Prevents phantom fixes from context compression.
---

# Code Modification Discipline

## Core Rule 1: Verify Before Reporting
**Before reporting a problem, verify it with an immutable command. Before fixing something, confirm it actually exists.**

### Trigger Condition: "X doesn't exist / X is broken"
When you intend to report "X doesn't exist" or "X is broken":

1. **First**, run this before saying anything:
   ```bash
   find . -name "X" -type d 2>/dev/null
   git log --all --oneline -- "X" 2>/dev/null
   ```
2. **Then** report what you found, not what you expected.

## Core Rule 2: Always Consult docs/ First
**Before any feature work, bugfix, or code decision, check if docs/ has relevant guidance.**

For ITOps Platform, the canonical sources are:
- `docs/01-architecture/AUTONOMOUS_ITOPS_TARGET_ARCHITECTURE.md` — target architecture
- `docs/05-implementation/DETAILED_REFACTOR_AND_GOVERNANCE_PLAN.md` — code decisions and governance

Trigger condition: Any time you receive a task that involves changing code, adding features, or deciding what to keep/refactor, **first** read the relevant section of these docs before proceeding. Do not assume you know what to do without checking.

### Trigger Condition: "X doesn't exist / X is broken"
When you intend to report "X doesn't exist" or "X is broken":

1. **First**, run this before saying anything:
   ```bash
   find . -name "X" -type d 2>/dev/null
   git log --all --oneline -- "X" 2>/dev/null
   ```
2. **Then** report what you found, not what you expected.

### Trigger Condition: "I need to fix X"
When you want to "fix" or "create" something to remedy a problem:
1. **First** confirm the problem exists with a command (not an assumption).
2. **Then** proceed with the fix.

### Rationale
LLM context compression causes "memory corridor effects" — reasoning steps and conclusions can become detached at context boundaries. The gap between "checked and found missing" and "concluded it was missing" can collapse, leading to phantom fixes for problems that were never confirmed to exist.

## Workflow for Code Changes
1. Run `python scripts/agent_self_check.py` + `head -50 docs/00-overview/README.md`
2. Verify problem with command before reporting
3. Plan fix — show user exact changes before executing
4. Execute one fix at a time
5. Verify fix with curl/API call
6. git commit immediately after each fix
7. Run `python scripts/verify_todo_accuracy.py` to confirm no TODO.md inconsistency introduced

## Core Rule 3: Mandatory Entry Check — Run agent_self_check.py First
**At the start of every new task in this project, before doing anything else:**

```bash
python scripts/agent_self_check.py
head -50 docs/00-overview/README.md
```

The guard script (scripts/agent_self_check.py) is the physical enforcement mechanism. It checks that:
- All 4 canonical docs exist (00-overview, AUTONOMOUS_ITOPS_TARGET_ARCHITECTURE, DETAILED_REFACTOR_AND_GOVERNANCE_PLAN, TODO.md)
- Current code directories exist (api/routes, modules/business, modules/collection)
- HERMES_RULES.md exists and contains the facts-source rule

If the script fails, do not proceed with any task.

**Trigger**: Any time you receive a new task, new requirements doc, or new review request.
- "I created X to fix Y, but X never actually existed in the first place"
- Reporting "file not found" without first running `find`
- "Fixing" symptoms instead of root causes
- Phantom directory/file creation from compressed context

## Emergency Rollback
If you suspect a phantom change was made:
```bash
git status
git diff HEAD
git stash list
find . -name "PHANTOM_DIR" -type d 2>/dev/null
```
