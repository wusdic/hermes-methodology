---
name: platform-module-design
description: "How to design a module for a multi-module ITOps platform — from current state analysis to detailed design doc. Covers: understanding existing code, defining module boundaries, mapping cross-module interfaces, and writing design documents. Use when starting a new module, refactoring an existing module with unclear boundaries, making boundary decisions about feature ownership, or designing module-to-module interfaces in a multi-module platform."
version: 1.0.0
metadata:
  hermes:
    tags: [platform-design, module-boundary, architecture, itops]
    related_skills: [systematic-debugging, complex-refactoring-planning]
---

# Platform Module Design Methodology

> How to design a module for a multi-module ITOps platform — from analysis to detailed design doc.
> This skill captures the methodology used for designing the ITOps Platform refactoring.

## When to Use

Use this skill when:
- Starting a new module for a multi-module platform
- Refactoring an existing module with unclear boundaries
- Making boundary decisions about which module should own a feature
- Designing module-to-module interfaces

## Core Principles

### 1. Single Module Responsibility
Each module owns exactly one domain. A module should not have "some features of domain X and some of domain Y."

### 2. Clear Entry Points
Every module has exactly ONE way to receive external requests:
- API routes (`api/routes/{module}.py`)
- Message queue consumers
- Event-driven triggers from other modules

### 3. Explicit Interfaces Over Implicit Coupling
Cross-module communication MUST go through:
- HTTP API calls (`POST /api/v1/other-module/...`)
- Defined service interfaces (not direct DB model imports)

### 4. Design Verification Before Implementation
Before writing code, the module design document must answer:
1. What is the module's core purpose? (one sentence)
2. What does the module own? (concrete list)
3. What does the module NOT own? (explicitly delegate)
4. What events can it receive? (entry points)
5. What events does it emit to other modules?
6. What DB tables does it manage?
7. What is the frontend page structure?

---

## Step-by-Step Design Process

### Step 0: Understand the Current State

Before designing, fully understand the existing code:

```
1. Read the route file (api/routes/{module}.py)
   - List ALL endpoints
   - Note which ones use in-memory storage (dicts/lists)
   - Note which ones call other modules

2. Read the business logic file (modules/business/{module}/)
   - List all classes and their responsibilities
   - Note which ones are just data classes vs have real logic

3. Read the DB models (modules/foundation/db_models/)
   - Check if required tables exist
   - Note missing tables

4. Read the frontend Vue files (frontend/src/views/{module}/)
   - List all API calls
   - Note mismatches between frontend calls and backend paths
```

### Step 1: Define Core Purpose (One Sentence)

Write the core purpose in one sentence. If you can't, the module boundary is unclear.

**Good examples:**
- "Automation module is the AI-driven execution engine that runs scripts in response to events."
- "Knowledge module is the documentation and case management system for operational experience."

**Bad examples:**
- "Automation module does scripts, tasks, executions, rollbacks, and notifications." (too many)
- "Knowledge module manages documents." (too vague)

### Step 2: List Owned Features (Concrete)

For each potential feature, ask:
- Does this feature make sense without any other module?
- Is this feature's data always accessed through this module?
- Would another module need to import this module's internals to use this feature?

If yes to all three → belongs in this module.

### Step 3: Identify Features to Delegate (Explicit)

For features that belong elsewhere, explicitly document:
- Which module should own it
- What interface the current module will use to call it
- What data format will be exchanged

### Step 4: Map Cross-Module Events

For each cross-module interaction, document:

```
Event: "Alert triggered"
From: monitoring module
To: automation module
Interface: POST /api/v1/automation/events
Payload: {event_type, event_id, context: {alert_level, device_id, ...}}
Response: {event_id, ai_decision: {decision, script_id, confidence, reason}}
```

### Step 5: Define Database Schema

For each table:
- Table name (snake_case, prefixed with module name)
- All columns with types
- Indexes
- Foreign keys
- Constraints

### Step 6: Design API Endpoints

Use consistent patterns:
```
GET/POST         /api/v1/{module}                    # List/Create
GET/PUT/DELETE   /api/v1/{module}/{id}              # Detail/Update/Delete
POST             /api/v1/{module}/{id}/sub-action   # Sub-action
```

### Step 7: Design Frontend Structure

Map frontend pages to API endpoints:
```
script.vue → /api/v1/automation/scripts (list/create/edit/delete)
            → /api/v1/automation/scripts/{id}/execute
task.vue   → /api/v1/automation/tasks
execute.vue → /api/v1/automation/executions
```

---

## Module Boundary Decision Framework

When two modules both seem to want the same feature, use this decision tree:

```
Feature F is being claimed by Module A and Module B.

1. Is F's data primarily created/read/updated/deleted by Module A's core workflow?
   → If yes, F belongs to A.

2. Does Module B need F's data to perform its own core workflow?
   → If yes, B calls A's API for F.

3. Is F a cross-cutting concern (notification, logging, auth)?
   → If yes, F might belong to a shared layer.

4. Is F about "doing X" vs "knowing about X"?
   → "Doing" → operational module
   → "Knowing" → knowledge/experience module
```

**Examples from ITOps Platform:**

| Feature | Decision | Reason |
|---------|---------|--------|
| SOP generation | Knowledge module | SOP is a document, not an action |
| Script recommendation | Knowledge module | Recommendation is about historical experience |
| Notification templates | Notification module | Templates are channel-specific |
| Escalation policies | Notification module | Escalation is about who to notify |
| Unified scheduler | New scheduler module | All modules need scheduling |
| Alert-to-automation trigger | Automation module | The trigger logic is "how to respond to alert" |

---

## Document Template

```markdown
# {Module} Module Design Document

## 1. Core Purpose (One Sentence)

## 2. Module Architecture

## 3. Features

### 3.1 Feature A
- Description
- Entry point (API/Event)
- DB tables
- Data flow

### 3.2 Feature B
...

## 4. Cross-Module Interfaces

### 4.1 {Module} → Other Module
```
Interface: POST /api/v1/other-module/...
Payload: {...}
Response: {...}
```

### 4.2 Other Module → {Module}
```
Interface: POST /api/v1/{module}/events
Payload: {...}
Response: {...}
```

## 5. Database Schema

```sql
CREATE TABLE module_things (...);
```

## 6. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/{module} | List |
| POST | /api/v1/{module} | Create |
| GET | /api/v1/{module}/{id} | Detail |
| PUT | /api/v1/{module}/{id} | Update |
| DELETE | /api/v1/{module}/{id} | Delete |

## 7. Frontend Pages

| Page | API | Description |
|------|-----|-------------|
| list.vue | GET /{module} | List page |
| detail.vue | GET /{module}/{id} | Detail page |

## 8. Security Considerations

## 9. Acceptance Criteria

1. [ ] Feature A works end-to-end
2. [ ] Cross-module call succeeds
3. [ ] Data persists across restart

## 10. File Checklist

| Action | File Path |
|--------|----------|
| New | scripts/migration/XXX_module.sql |
| New | modules/foundation/db_models/{module}.py |
| Modify | api/routes/{module}.py |
| Modify | frontend/src/views/{module}/... |
```

---

## Common Pitfalls

### Pitfall 1: "We'll figure out the interface later"
Always design the cross-module interface BEFORE implementing either module. The interface IS part of the design.

### Pitfall 2: Data model first, purpose second
Start with the core purpose. If you can't state it clearly, you don't understand the module well enough to design it.

### Pitfall 3: Over-designing the "perfect" boundary
Module boundaries will evolve. Start with a reasonable boundary and refine in subsequent iterations.

### Pitfall 4: Forgetting the frontend
The backend API must match what the frontend expects. Always audit the frontend Vue files to understand what API calls are being made.

### Pitfall 5: In-memory storage as "temporary"
If data lives in a Python dict/list, it WILL be lost on restart. Always ask: "Should this data persist?" If yes, design a DB table.

---

## Verification Checklist

Before considering the design complete, verify:

- [ ] Core purpose is stated in one sentence
- [ ] All features are listed and ownership is clear
- [ ] Cross-module interfaces are explicitly designed (not "TBD")
- [ ] All DB tables are defined with columns and indexes
- [ ] All API endpoints are listed with request/response formats
- [ ] Frontend pages are mapped to API calls
- [ ] In-memory storage cases are identified and addressed
- [ ] Security considerations are documented
- [ ] Acceptance criteria are concrete and testable
- [ ] File checklist covers all new and modified files
