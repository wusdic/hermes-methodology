# Target repo decision tree

Concrete rules for "should this skill go to `hermes-methodology`,
`qa-momentum`, or stay local?"

## User's actual repos (as of 2026-06)

| Repo | Purpose | Default host for |
|------|---------|------------------|
| `wusdic/hermes-methodology` (4.2MB) | Hermes Agent Skills - Methodology and Best Practices | 90% of publishable skills |
| `wusdic/qa-momentum` (19KB, mostly empty) | QA Methodology and Best Practices Skill System | QA testing, code review, verification |
| `wusdic/hermes-kanban-platform` | Hermes Kanban multi-project platform (project repo) | Anything kanban-orchestration related → also a project repo, NOT a method repo |
| `wusdic/autocode-platform` | Multi-project autonomous coding platform (project repo) | Same — project, not method |
| `wusdic/itops-platform` | ITOps Platform (project repo) | Project-specific; do NOT publish skills into this repo |
| `wusdic/autops-zhipu` | AUTOPS AIOps platform (project repo) | Project-specific; do NOT publish |
| `wusdic/stt-whisper` | Whisper STT (project repo) | Project-specific |
| `wusdic/data-collector` | Data collection (project repo) | Project-specific |
| `wusdic/caijifagui` | 法规查漏补缺能力库 (project repo) | Project-specific |
| `wusdic/it-device-kb-platform` | IT device KB (project repo, Go) | Project-specific |

## Routing rules

**The two "method" repos are `hermes-methodology` and `qa-momentum` only.**

Everything else is a *project* repo, not a *method* repo. Don't dump
methodology skills into project repos — that conflates "this project's code"
with "this reusable lesson".

## Quick routing (path → destination)

```
~/.hermes/skills/<path>                        → destination in hermes-methodology
```

| Path pattern | Destination |
|--------------|-------------|
| `methodology/*` | `methodology/<skill-name>/` |
| `devops/hermes-*` | `devops/<skill-name>/` (Hermes-internal DevOps) |
| `devops/kanban-*` | `devops/<skill-name>/` (or keep in kanban-platform repo) |
| `devops/*` (generic DevOps) | `devops/<skill-name>/` |
| `best-practices/backend/*` | `best-practices/backend/<skill-name>/` |
| `best-practices/devops/*` | `best-practices/devops/<skill-name>/` |
| `best-practices/*` (other) | `best-practices/<sub>/<skill-name>/` |
| `software-development/*` | `software-development/<skill-name>/` |
| `frontend/*` | `frontend/<skill-name>/` |
| `backend/*` (root-level gotchas) | `best-practices/backend/<skill-name>/` (re-organize) |
| `creative/*` | `creative/<skill-name>/` |
| `productivity/*` | `productivity/<skill-name>/` |
| `mlops/*` | `mlops/<skill-name>/` |
| `web/*` | `web/<skill-name>/` |
| `*pagination-debugging`, `*table-debugging`, `*workaround` (root-level) | `frontend/<skill-name>/` (re-organize) |
| `itops/*`, `projects/itops-*`, `itops-platform-*` | ❌ **DO NOT publish** — project-specific |
| `autops-*` | ❌ **DO NOT publish** — project-specific |
| `apple/*`, `yuanbao/*`, `*computer-use` | Ask user (may be personal tooling) |

## What about `qa-momentum`?

The user has a dedicated `qa-momentum` repo for "QA Methodology". Skills that
fit:

- `methodology/systematic-qa-testing` → yes
- `methodology/requesting-code-review` → yes
- `methodology/test-driven-development` → yes
- `methodology/docx-static-analysis-to-live-verification` → yes (QA evidence)
- `itops/itops-platform-api-verification` → ❌ (project-specific)
- `projects/itops-platform-frontend-verification` → ❌ (project-specific)

## What about cross-repo links?

`hermes-methodology` and `qa-momentum` are separate repos. If a skill
references another skill (e.g. `systematic-qa-testing` references
`systematic-debugging`), use the **full GitHub URL**, not a relative path:

```markdown
Related: [systematic-debugging](https://github.com/wusdic/hermes-methodology/tree/main/methodology/systematic-debugging)
```

This way the skills work as standalone units and don't break if a future
session reorganizes the directory structure.

## Versioning

Don't tag releases in `hermes-methodology` — it's a content repo, not a
library. Just commit to `main`. If a particular skill version matters (e.g.
"works only with Hermes Agent v0.15.1+"), put that in the SKILL.md frontmatter
`version` field, not in a Git tag.
