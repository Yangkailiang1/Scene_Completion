"""On-demand loading for the concern knowledge base."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .concerns import ACTIVE_CONCERN_KEYS, CONCERN_DEFINITIONS, list_concerns


def _concerns_dir() -> Path:
    return Path(__file__).resolve().parents[3] / ".cac" / "skills" / "scene-review" / "references" / "concerns_v2"


def load_concern(key: str) -> dict[str, Any]:
    normalized = str(key).strip().lower()
    if normalized not in ACTIVE_CONCERN_KEYS:
        raise ValueError(f"unknown concern: {key}")
    path = _concerns_dir() / f"{normalized.replace('.', '__')}.md"
    if not path.exists() and normalized.startswith("service."):
        # The business-service definitions were historically stored under an
        # SR-specific filename; the key is now layer-neutral by design.
        path = _concerns_dir() / f"sr_service__{normalized.removeprefix('service.').replace('.', '__')}.md"
    if not path.exists():
        raise FileNotFoundError(f"concern reference not found: {path}")
    definition = dict(CONCERN_DEFINITIONS[normalized])
    definition.update({"reference": str(path), "content": path.read_text(encoding="utf-8")})
    return definition


def list_diagram_knowledge() -> list[dict[str, str]]:
    return [
        {"key": "system_composition", "reference": ".cac/skills/scene-assemble/references/system_composition.md", "focus": "系统组成节点和关系"},
        {"key": "interaction_concern", "reference": ".cac/skills/scene-ssd/references/diagrams_v2/interaction_concern.md", "focus": "用例、交互和关注点状态"},
    ]


def load_diagram_knowledge(key: str) -> dict[str, str]:
    normalized = str(key).strip().lower()
    references = {item["key"]: item for item in list_diagram_knowledge()}
    if normalized not in references:
        raise ValueError(f"unknown diagram knowledge: {key}")
    path = Path(__file__).resolve().parents[3] / references[normalized]["reference"]
    return {**references[normalized], "reference": str(path), "content": path.read_text(encoding="utf-8")}


__all__ = ["list_concerns", "load_concern", "list_diagram_knowledge", "load_diagram_knowledge"]
