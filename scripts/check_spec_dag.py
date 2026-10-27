#!/usr/bin/env python3
"""Check that specs/*/tasks.md task dependencies form a valid DAG.

Usage: check_spec_dag.py [--strict] [--ready] [SPECS_DIR]

--ready lists open tasks whose dependencies and sub-tasks are all done (READY lines).

Task line:   - [ ] T010 Description          (sub-tasks are indented: T050a, T050c1)
Dependency:    - depends_on: [T001, 005:T061]   (bare ID = same spec; NNN:ID = other spec)
Spec deps:   "Depends on Spec NNN" in tasks.md, or "Spec NNN" on spec.md's **Depends on:** line.

Errors (exit 1): undefined dependency, cycle, task done while a dependency is open,
parent done while a sub-task is open, duplicate ID, literal "\\n" in a task line,
missing spec dependency target.
Warnings (exit 1 only with --strict): spec-prefixed task IDs, a dependency listed after
the task that needs it, a feature missing spec.md / plan.md / tasks.md.
"""
import os
import re
import sys
from pathlib import Path

TASK = re.compile(r"^(\s*)- \[([ xX])\] (?:(\d{3})-)?(T\d{3}[a-z0-9]*)\b(.*)$")
DEPS = re.compile(r"^\s*- depends_on: \[(.*)\]\s*$")
SPEC_DEP = re.compile(r"\bSpec (\d{3})\b")
REQUIRED = ("spec.md", "plan.md", "tasks.md")


def parse(specs: Path):
    tasks, spec_deps, errors, warnings = {}, {}, [], []
    for d in sorted(p for p in specs.iterdir() if p.is_dir() and re.match(r"\d{3}-", p.name)):
        num = d.name[:3]
        for name in REQUIRED:
            if not (d / name).exists():
                warnings.append(f"{d}/: SPECKIT missing {name}")
        spec_deps[num] = set()
        spec_md = d / "spec.md"
        if spec_md.exists():
            for line in spec_md.read_text().splitlines():
                if line.startswith("**Depends on:**"):
                    spec_deps[num] |= set(SPEC_DEP.findall(line))
        tasks_md = d / "tasks.md"
        if not tasks_md.exists():
            continue
        stack, last = [], None  # stack of (indent, key)
        for n, line in enumerate(tasks_md.read_text().splitlines(), 1):
            where = f"{tasks_md}:{n}"
            if "Depends on Spec" in line:
                spec_deps[num] |= set(SPEC_DEP.findall(line))
            m = TASK.match(line)
            if m:
                indent, mark, prefix, tid, rest = m.groups()
                key = f"{num}:{tid}"
                if prefix:
                    warnings.append(f"{where}: ID-PREFIX {prefix}-{tid} (Spec Kit uses bare {tid})")
                    if prefix != num:
                        errors.append(f"{where}: ID-PREFIX {prefix}-{tid} does not match spec {num}")
                if "\\n" in rest:
                    errors.append(f"{where}: LITERAL-NEWLINE task line contains a literal \\n")
                if key in tasks:
                    errors.append(f"{where}: DUPLICATE {tid} (first at line {tasks[key]['line']})")
                while stack and stack[-1][0] >= len(indent):
                    stack.pop()
                parent = stack[-1][1] if stack else None
                tasks[key] = {
                    "done": mark != " ",
                    "deps": [],
                    "line": where,
                    "parent": parent,
                    "order": n,
                    "text": rest.strip(),
                }
                stack.append((len(indent), key))
                last = key
                continue
            m = DEPS.match(line)
            if m and last:
                for ref in filter(None, (r.strip() for r in m.group(1).split(","))):
                    tasks[last]["deps"].append(ref if ":" in ref else f"{num}:{ref}")
    return tasks, spec_deps, errors, warnings


def find_cycle(graph):
    state, path = {}, []

    def visit(node):
        state[node] = 1
        path.append(node)
        for nxt in sorted(graph.get(node, ())):
            if state.get(nxt) == 1:
                return path[path.index(nxt):] + [nxt]
            if nxt not in state and (cycle := visit(nxt)):
                return cycle
        state[node] = 2
        path.pop()
        return None

    for node in sorted(graph):
        if node not in state and (cycle := visit(node)):
            return cycle
    return None


def check(specs: Path):
    tasks, spec_deps, errors, warnings = parse(specs)
    for num, deps in spec_deps.items():
        for dep in sorted(deps - {num}):
            if dep not in spec_deps:
                errors.append(f"{specs}/{num}-*: SPEC-DEP Spec {dep} does not exist")
    if cycle := find_cycle({k: v - {k} for k, v in spec_deps.items()}):
        errors.append(f"{specs}: SPEC-CYCLE " + " -> ".join(cycle))

    for key, t in tasks.items():
        for dep in t["deps"]:
            if dep not in tasks:
                errors.append(f"{t['line']}: UNDEFINED {key} depends on {dep}")
                continue
            if t["done"] and not tasks[dep]["done"]:
                errors.append(f"{t['line']}: DONE-BEFORE-DEP {key} is done but {dep} is open")
            same_file = dep.split(":")[0] == key.split(":")[0]
            if same_file and tasks[dep]["order"] > t["order"]:
                warnings.append(f"{t['line']}: ORDER {key} is listed before its dependency {dep}")
        parent = t["parent"]
        if parent and tasks[parent]["done"] and not t["done"]:
            errors.append(f"{tasks[parent]['line']}: DONE-BEFORE-CHILD {parent} is done but {key} is open")
    if cycle := find_cycle({k: {d for d in t["deps"] if d in tasks} for k, t in tasks.items()}):
        errors.append(f"{specs}: TASK-CYCLE " + " -> ".join(cycle))
    return tasks, errors, warnings


def ready(tasks):
    """Open tasks whose dependencies and sub-tasks are all done, in file order.

    An undefined dependency counts as not done, so a task blocked by a missing ID is
    never reported ready.
    """
    open_children = {t["parent"] for t in tasks.values() if t["parent"] and not t["done"]}
    return [
        key
        for key, t in sorted(tasks.items(), key=lambda kv: (kv[0].split(":")[0], kv[1]["order"]))
        if not t["done"]
        and key not in open_children
        and all(d in tasks and tasks[d]["done"] for d in t["deps"])
    ]


def main(argv):
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    strict = "--strict" in argv
    show_ready = "--ready" in argv
    args = [a for a in argv if a not in ("--strict", "--ready")]
    specs = Path(args[0]) if args else Path(__file__).resolve().parent.parent / "specs"
    specs = Path(os.path.relpath(specs))
    tasks, errors, warnings = check(specs)
    for msg in errors:
        print(f"ERROR {msg}")
    for msg in warnings:
        print(f"WARN  {msg}")
    if show_ready:
        for key in ready(tasks):
            print(f"READY {key} {tasks[key]['text']}")
    done = sum(t["done"] for t in tasks.values())
    print(f"{len(tasks)} tasks ({done} done), {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors or (strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
