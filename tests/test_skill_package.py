import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPOSITORY_ROOT / ".cac" / "skills"
SKILL_NAMES = {
    "scene-extract", "scene-ssd", "scene-review", "scene-assemble",
    "dependency-graph", "test-scenario-extract", "scenario-match",
    "scene-generate", "scene-check", "scene-recommend",
}


def _frontmatter(path: Path) -> tuple[str, str]:
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    _, raw, body = content.split("---", 2)
    return raw, body


def test_each_skill_has_valid_frontmatter_and_local_references():
    for name in SKILL_NAMES:
        skill_root = SKILLS_ROOT / name
        raw, body = _frontmatter(skill_root / "SKILL.md")
        fields = dict(re.findall(r"(?m)^([A-Za-z_-]+):\s*(.*?)\s*$", raw))
        assert fields.get("name") == name
        assert fields.get("description")
        for ref in re.findall(r"`(references/[^`]+\.md)`", body):
            assert (skill_root / ref).is_file(), f"{name}: missing {ref}"
    assert not (SKILLS_ROOT / "scene-completion" / "SKILL.md").exists()
    assert (REPOSITORY_ROOT / ".cac" / "tools" / "scene_completion.py").is_file()


def test_scene_agent_declares_only_existing_skills_and_pipeline_gates():
    raw, body = _frontmatter(REPOSITORY_ROOT / ".cac" / "agents" / "scene-agent.md")
    declared = set(re.findall(r"(?m)^\s+-\s+([\w-]+)\s*$", raw))
    assert declared == SKILL_NAMES
    assert "pending" in body
    assert "scenario-match" in body


def test_dependency_graph_skill_keeps_full_algorithm_reference():
    reference = SKILLS_ROOT / "dependency-graph" / "references" / "crud-dependency-algorithm.md"
    content = reference.read_text(encoding="utf-8")
    for heading in ("核心公理", "依赖判定规则", "边的来源标注", "依赖关系四元组", "提示词模板", "不应做的事"):
        assert heading in content
    assert len(content.splitlines()) > 150
