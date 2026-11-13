"""Guard the architectural boundaries that a directory-only move cannot enforce."""

import ast

from tests.support.paths import ROOT

PACKAGE = ROOT / "src/scene_completion"


def imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
            yield from (node.module + "." + alias.name for alias in node.names)


def test_domain_is_independent_of_business_and_delivery_adapters():
    violations = []
    for path in (PACKAGE / "domain").rglob("*.py"):
        for name in imports(path):
            if name.startswith("scene_completion.") and not name.startswith(
                ("scene_completion.domain", "scene_completion.infrastructure.identity")
            ):
                violations.append(f"{path.relative_to(ROOT)}: {name}")
    assert not violations, "\n".join(violations)


def test_shared_identity_has_no_storage_or_business_dependency():
    path = PACKAGE / "infrastructure/identity.py"
    assert set(imports(path)) == {"hashlib", "json"}
    tree = ast.parse(path.read_text())
    assert not any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"
        for node in ast.walk(tree)
    )


def test_ssd_implementation_does_not_import_detailed_compatibility_workflow():
    paths = [*(PACKAGE / "analysis/ssd").rglob("*.py"), PACKAGE / "workflow/ssd_pipeline.py"]
    assert not [
        (str(path), name)
        for path in paths
        for name in imports(path)
        if name.startswith("scene_completion.compat.detailed")
    ]


def test_services_and_manager_do_not_depend_on_cli_or_http_assembly():
    paths = [*(PACKAGE / "application").rglob("*.py"), *(PACKAGE / "manager").glob("*.py")]
    assert not [
        (str(path), name)
        for path in paths
        for name in imports(path)
        if name.startswith(("scene_completion.cli", "scene_completion.api"))
    ]


def test_input_and_model_services_are_not_defined_in_delivery_modules():
    for relative, forbidden in {
        "api/inputs.py": {"scan", "accept_source", "InputWatcher", "watch_settings"},
        "cli/task_commands.py": {"client_for"},
    }.items():
        tree = ast.parse((PACKAGE / relative).read_text())
        definitions = {
            node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }
        assert not definitions & forbidden
