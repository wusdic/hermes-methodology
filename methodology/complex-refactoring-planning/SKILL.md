---
name: complex-refactoring-planning
description: Plan and execute large-scale codebase refactoring (100+ files, multi-module) with upfront design docs and phased delivery
---

# Complex Refactoring Planning Skill

## When to Use

Use this skill when asked to plan or execute a large-scale codebase refactoring. Indicators:
- 100+ files involved
- Multiple modules/domains affected
- User says "极其复杂" (extremely complex) or similar
- User explicitly demands "设计清楚够细致" (design clearly and thoroughly before coding)
- Two or more design documents involved as input

## Core Principle

**Plan first, code second.** For complex refactoring, the planning document IS the deliverable. Rushing to code without a spec leads to patch-on-patch (屎山).

## Step-by-Step Process

### Step 0: Understand the Scope

Before writing any plan:
1. **Count the codebase**: files, LOC, largest modules
2. **Read the design documents**: parse .docx via `zipfile` + `xml.etree.ElementTree`
3. **Audit existing code**: identify actual file paths, API routes, data models
4. **Identify P0 blockers**: problems that prevent core workflows from running

```
Command reference:
- Count: find . -name "*.py" | wc -l
- Audit routes: ls api/routes/*.py
- Find models: grep -r "class.*Base" modules/
```

### Step 1: Produce the SPEC.md

Create `/docs/REFACTORING_DESIGN.md` with these sections:

1. **现状评估** — Current state, code metrics, module coverage matrix
2. **重构目标** — Product positioning, core closed loops (must be demo-able)
3. **总体架构** — Target layered architecture with clear boundaries
4. **模块级重构方案** — Each module: current state, target state, new data models, new APIs
5. **实施计划** — Phased plan with milestones and acceptance criteria
6. **重构规范** — Coding standards (data models, API responses, layer constraints)
7. **已验证可行的改动（保留）** — What was already fixed and must not be reverted
8. **风险与约束** — Known risks, dependencies

### Step 2: Gap Analysis — Handle Tool Failures Gracefully

When a tool fails (e.g., doc parsing returns empty):
- Do NOT keep retrying the same failing tool repeatedly
- Work around: use the already-parsed document + direct code inspection
- Document the blocked item and proceed with available information

### Step 3: Present SPEC and Get User Confirmation

The SPEC is the mandatory deliverable before any code is written. Include:
- Exact file path where the spec was saved
- Summary of what's covered
- Specific decision points that need user input
- Explicit risks and constraints

Ask the user to confirm: which module to start with? Phased or batch?

### Step 4: Incremental Execution

Execute module-by-module, not all-at-once:
- Start with P0 blockers (things blocking core demos)
- Each module: design → implement → verify
- Preserve already-working functionality (auth, collection)

## Lessons Learned (Pitfalls)

### Pitfall: Docx Parsing Fails Silently
- **Symptom**: `execute_code` and `terminal` both return empty output for a valid .docx file
- **Workaround**: Use `zipfile` + `xml.etree.ElementTree` via a fresh terminal session; ensure working directory is correct
- **Prevention**: Verify file exists with `ls -la` before attempting to parse

### Pitfall: Over-estimating What Can Be Done in One Session
- Complex refactoring spans weeks/months. Set realistic expectations.
- User directive "功能修好后立即停止，不要继续改代码" applies to bug fixes — clarify scope boundaries for refactoring separately.

### Pitfall: Path Resolution Confusion
- **Symptom**: Display artifacts show phantom directories (e.g., `api/routes/api/routes/`)
- **Fix**: Always verify with `find` or `ls` from the actual root directory
- **Prevention**: Trust `ls/find` output over large file listing displays

## Output Format for SPEC.md

```
# [Project] 重构设计文档

## 一、现状评估
...

## 二、重构目标
...

## 三、总体架构
...

## 四、模块级重构方案
...

## 五、实施计划
...

## 六、重构规范
...

## 七、已验证可行的改动（保留）
...

## 八、风险与约束
...
```

## Verification Steps

After creating the SPEC.md:
1. Confirm file exists at the specified path
2. Confirm file size > 5KB (indicates substantial content)
3. Present user with summary and ask for direction

## Related Skills

- `code-modification-discipline`: Use when modifying existing code — force documentation of impact, root cause, and verification
- `systematic-debugging`: Use when encountering bugs during refactoring
