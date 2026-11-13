"""SSD business rules cannot depend on delivery, execution or persistence adapters."""

import ast

from tests.support.paths import ROOT


def test_ssd_domain_imports_only_domain_or_external_dependencies():
    package = ROOT / "src/scene_completion/domain/ssd"
    violations = []
    for path in sorted(package.glob("*.py")):
        module = "scene_completion.domain.ssd." + path.stem
        for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                name = node.module or ""
                if node.level:
                    name = ".".join(module.split(".")[: -node.level] + ([name] if name else []))
                names = [name]
            else:
                continue
            violations.extend(
                f"{path.name}:{node.lineno}: {name}"
                for name in names
                if name.startswith("scene_completion")
                and not name.startswith("scene_completion.domain")
                and name != "scene_completion.infrastructure.identity"
            )
    assert not violations, "\n".join(violations)
