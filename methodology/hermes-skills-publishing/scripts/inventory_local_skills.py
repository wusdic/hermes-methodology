#!/usr/bin/env python3
"""
Inventory all Hermes Agent skills under a root directory (default ~/.hermes/skills/).
Produces:
  - A categorized Markdown report (printed + optional --output)
  - A structured JSON sidecar (always written next to the markdown)

Auto-classifies each skill as one of:
  A. Project-specific (excluded by default from publish)
  B. Hermes/methodology (strong candidate)
  C. Gotcha/pitfall
  D. DevOps tool
  E. Other generic

Usage:
  python3 inventory_local_skills.py
  python3 inventory_local_skills.py --root /custom/path --output /tmp/report.md
"""
import argparse, json, os, re, sys
from pathlib import Path
from collections import defaultdict

def parse_skill_md(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")[:3000]
    except Exception:
        return {"name": "?", "description": "", "tags": [], "category": ""}
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return {"name": "?", "description": "", "tags": [], "category": ""}
    fm = m.group(1)
    out = {}
    for k in ("name", "description", "version", "author"):
        mm = re.search(rf"^{k}:\s*(.+?)$", fm, re.MULTILINE)
        out[k] = mm.group(1).strip().strip('"').strip("'") if mm else ""
    mm = re.search(r"^tags:\s*\[(.*?)\]", fm, re.MULTILINE | re.DOTALL)
    if mm:
        out["tags"] = [t.strip().strip('"').strip("'")
                       for t in mm.group(1).split(",") if t.strip()]
    else:
        out["tags"] = []
    mm = re.search(r"^category:\s*(.+?)$", fm, re.MULTILINE)
    out["category"] = mm.group(1).strip() if mm else ""
    return out

def collect(root: Path) -> list:
    out = []
    for skill_dir in sorted(root.iterdir()):
        if not skill_dir.is_dir():
            continue
        for sub in [skill_dir] + list(skill_dir.iterdir()):
            if sub.is_dir() and (sub / "SKILL.md").exists():
                fm = parse_skill_md(sub / "SKILL.md")
                if fm:
                    rel = str(sub.relative_to(root))
                    out.append({
                        "name": fm.get("name") or sub.name,
                        "path": rel,
                        "description": fm.get("description", ""),
                        "category": fm.get("category", ""),
                        "tags": fm.get("tags", []),
                        "author": fm.get("author", ""),
                        "size_kb": round((sub / "SKILL.md").stat().st_size / 1024, 1),
                    })
    return out

PROJECT_KEYWORDS = ["itops", "autops", "naive-ui-to-element-plus", "it-device-kb"]
HERMES_KEYWORDS = ["hermes-", "methodology/"]
GOTCHA_KEYWORDS = ["debugging", "fix", "gotcha", "workaround"]

def is_project_specific(s: dict) -> bool:
    """Path-segment + description-text project-specific detector.

    A skill is project-specific if ANY of:
      - any path segment is exactly "itops", "itops_platform", or "autops"
      - any path segment starts with "itops-" (catches projects/itops-foo)
      - path contains "naive-ui-to-element-plus"
      - description contains "ITOps Platform" (catches e.g. methodology/
        platform-module-design which is project-specific despite its generic name)
    """
    p = s["path"].lower()
    parts = p.split("/")
    for part in parts:
        if part in ("itops", "itops_platform", "autops") or part.startswith("itops-"):
            return True
    if "naive-ui-to-element-plus" in p:
        return True
    desc = (s.get("description") or "").lower()
    if "itops platform" in desc:
        return True
    return False

def classify(s: dict) -> str:
    if is_project_specific(s):
        return "A_project_specific"
    p = s["path"].lower()
    if any(k in p for k in HERMES_KEYWORDS):
        return "B_hermes_methodology"
    if any(k in p for k in GOTCHA_KEYWORDS):
        return "C_gotcha_pitfall"
    if p.startswith("devops/"):
        return "D_devops_tool"
    return "E_other_generic"

CLASS_DESC = {
    "A_project_specific": "🔧 A. Project-specific (excluded by default)",
    "B_hermes_methodology": "🛠️ B. Hermes/methodology (strong candidate)",
    "C_gotcha_pitfall":     "🐛 C. Gotcha/pitfall",
    "D_devops_tool":        "🔧 D. DevOps tool",
    "E_other_generic":      "📦 E. Other generic",
}

def build_report(skills: list, root: Path) -> str:
    by_top = defaultdict(list)
    for s in skills:
        by_top[s["path"].split("/")[0]].append(s)
    by_class = defaultdict(list)
    for s in skills:
        by_class[classify(s)].append(s)

    L = []
    L.append(f"# Hermes Skills Inventory (共 {len(skills)} skills)\n")
    L.append(f"Root: {root}\n\n")
    L.append("=" * 100 + "\n📑 By directory\n" + "=" * 100 + "\n")
    for top in sorted(by_top):
        L.append(f"\n## 📁 {top}/  ({len(by_top[top])} skills)\n")
        for s in sorted(by_top[top], key=lambda x: x["path"]):
            sub = s["path"][len(top) + 1:]
            label = f" → {sub}" if "/" in s["path"] else ""
            desc = s["description"][:80] + ("…" if len(s["description"]) > 80 else "")
            cat = f" [{s['category']}]" if s["category"] and s["category"] != top else ""
            L.append(f"  - **{s['name']}**{label} ({s['size_kb']}KB){cat}\n")
            if s["description"]:
                L.append(f"    > {desc}\n")
    L.append("\n" + "=" * 100 + "\n🎯 By content type\n" + "=" * 100 + "\n")
    for cls in sorted(CLASS_DESC):
        items = by_class.get(cls, [])
        if not items:
            continue
        L.append(f"\n### {CLASS_DESC[cls]} — {len(items)} 项\n")
        for s in sorted(items, key=lambda x: x["path"]):
            L.append(f"  - **{s['name']}** — `{s['path']}` — {s['description'][:60]}\n")
    return "".join(L)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("~/.hermes/skills"))
    ap.add_argument("--output", default=None,
                    help="Path for Markdown report (default: stdout)")
    ap.add_argument("--json", default=None,
                    help="Path for JSON sidecar (default: alongside --output)")
    args = ap.parse_args()
    root = Path(args.root)
    if not root.is_dir():
        sys.exit(f"❌ Not a directory: {root}")
    skills = collect(root)
    report = build_report(skills, root)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        json_path = args.json or (str(args.output).rsplit(".", 1)[0] + ".json")
        Path(json_path).write_text(json.dumps(skills, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"✅ Wrote {args.output} + {json_path}  ({len(skills)} skills)")
    else:
        print(report)

if __name__ == "__main__":
    main()
