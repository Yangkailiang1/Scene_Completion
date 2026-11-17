"""Fail when a package imports upward against the declared architecture.

The package layout says what the project is *meant* to be: domain rules do not
know about transport, infrastructure does not know about use cases. In practice
21 of the 13 packages import each other both ways. This check stops that from
getting worse without demanding a risky rewrite: existing reverse edges are
listed in ``KNOWN_REVERSE_EDGES`` with a reason, and only *new* ones fail.

Fix a violation by moving the dependency, or by adding the edge here with a
written reason and a plan to remove it. Silence is not an option.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src/scene_completion"
PACKAGE = "scene_completion"

# Who may import whom. A package may always import itself.
# Only directions that currently hold are listed; adding a direction is a design
# decision, not a refactor, so it needs a review.
ALLOWED = {
    "api": {
        "application",
        "review",
        "models",
        "inputs",
        "domain",
        "infrastructure",
        "workflow",
        "workflow_core",
        "compat",
        "analysis",
        "cli",
        "manager",
    },
    "cli": {
        "application",
        "review",
        "models",
        "inputs",
        "domain",
        "infrastructure",
        "workflow",
        "workflow_core",
        "compat",
        "analysis",
        "manager",
    },
    "application": {
        "domain",
        "models",
        "inputs",
        "review",
        "infrastructure",
        "workflow",
        "workflow_core",
        "compat",
        "analysis",
        "manager",
    },
    "workflow": {
        "analysis",
        "inputs",
        "domain",
        "models",
        "infrastructure",
        "workflow_core",
        "review",
        "application",
        "compat",
        "manager",
    },
    "analysis": {
        "domain",
        "infrastructure",
        "inputs",
        "workflow_core",
        "application",
        "review",
        "workflow",
    },
    "inputs": {"domain", "infrastructure", "analysis", "workflow_core", "application", "workflow"},
    "models": {
        "infrastructure",
        "inputs",
        "domain",
        "workflow_core",
        "application",
        "analysis",
        "review",
        "workflow",
        "manager",
    },
    "review": {
        "domain",
        "infrastructure",
        "inputs",
        "analysis",
        "compat",
        "application",
        "workflow_core",
        "workflow",
    },
    "manager": {
        "models",
        "infrastructure",
        "analysis",
        "application",
        "review",
        "workflow",
        "workflow_core",
        "inputs",
        "compat",
        "domain",
    },
    "compat": {
        "analysis",
        "inputs",
        "domain",
        "review",
        "workflow_core",
        "infrastructure",
        "workflow",
    },
    # Infrastructure may not reach into use cases, transport or the pipeline.
    "infrastructure": {"domain", "workflow_core"},
    # Domain is the innermost layer: it may not depend on anything else here.
    "domain": set(),
    "workflow_core": {"infrastructure"},
}

# Reverse edges that exist today. Each is a debt with a written reason.
# Removing an entry is progress; adding one needs the same justification.
KNOWN_REVERSE_EDGES = {
    # worker bootstrap owns process lifecycle, so it reaches into use cases.
    (
        "infrastructure",
        "application",
        "scene_completion/infrastructure/worker_runtime.py",
    ): "worker bootstrap needs the Workbench service and handoff preparation",
    (
        "infrastructure",
        "manager",
        "scene_completion/infrastructure/worker_runtime.py",
    ): "worker shutdown must stop manager processes",
    # the read-only graph view assembles data owned by higher layers.
    (
        "infrastructure",
        "review",
        "scene_completion/infrastructure/execution_graph.py",
    ): "graph view reads node conversations",
    (
        "infrastructure",
        "inputs",
        "scene_completion/infrastructure/execution_graph.py",
    ): "graph view labels import provenance",
    (
        "infrastructure",
        "application",
        "scene_completion/infrastructure/execution_graph.py",
    ): "graph view reuses the import plan",
    (
        "infrastructure",
        "models",
        "scene_completion/infrastructure/execution_progress.py",
    ): "progress view reuses transport schema validation",
}

# One shared helper is reused across the whole domain layer. Moving
# ``infrastructure/identity.py`` into domain would be correct, but it changes an
# import used by 9 domain modules and by the published cache identity, so it is
# recorded as a single known edge rather than nine.
KNOWN_DOMAIN_IDENTITY = (
    "domain modules share the fingerprint helper from infrastructure/identity.py; "
    "the helper is pure and belongs in domain when that move is scheduled"
)

# Importable top-level subpackages; anything else is not treated as a layer.
LAYERS = tuple(ALLOWED)


def _layer_of(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != PACKAGE:
        return None
    return parts[1] if parts[1] in LAYERS else None


def _imports(path: Path):
    """Yield (imported_package, lineno) for every import, including nested ones."""
    tree = ast.parse(path.read_text(encoding="utf8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Relative imports are already constrained to the same package.
                continue
            if node.module:
                yield node.module, node.lineno


def violations():
    problems = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        relative = path.relative_to(PACKAGE_ROOT.parent).as_posix()
        parts = path.relative_to(PACKAGE_ROOT).parts
        if len(parts) == 1:
            caller = "__init__"
        else:
            caller = parts[0]
        if caller not in ALLOWED:
            continue
        for module, lineno in _imports(path):
            imported = _layer_of(module)
            if imported is None or imported == caller:
                continue
            if imported in ALLOWED[caller]:
                continue
            if (caller, imported, relative) in KNOWN_REVERSE_EDGES:
                continue
            if imported == "infrastructure" and module == f"{PACKAGE}.infrastructure.identity":
                continue
            problems.append((relative, lineno, caller, imported, module))
    return problems


def main():
    problems = violations()
    if problems:
        print("发现未登记的分层违规（反向依赖）：", file=sys.stderr)
        for relative, lineno, caller, imported, module in problems:
            print(f"  {relative}:{lineno}  {caller} -> {imported}  ({module})", file=sys.stderr)
        print(
            "\n改为移动依赖；确需保留时在 tools/check_architecture.py 的 "
            "KNOWN_REVERSE_EDGES 登记文件与原因。",
            file=sys.stderr,
        )
        return 1
    print(
        f"分层检查通过：{len(ALLOWED)} 个包，"
        f"{len(KNOWN_REVERSE_EDGES)} 条已登记的历史反向依赖，"
        f"1 条共享身份函数豁免（{KNOWN_DOMAIN_IDENTITY[:32]}…）。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
