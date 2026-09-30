import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / ".cac" / "skills" / "scene-completion"


def test_skill_package_contract_and_referenced_knowledge_files_exist():
    skill_file = SKILL_ROOT / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    frontmatter = content.split("---", 2)[1]
    fields = dict(re.findall(r"(?m)^([A-Za-z_-]+):\s*(.*?)\s*$", frontmatter))

    assert fields.get("name") == SKILL_ROOT.name
    assert fields.get("description")
    assert fields.get("title")
    assert fields.get("version")
    assert (SKILL_ROOT / "scripts" / "scene_completion.py").is_file()
    assert (SKILL_ROOT / "scripts" / "scene_completion" / "__init__.py").is_file()

    references = re.findall(r"`(references/[^`]+\.md)`", content)
    assert references
    assert all((SKILL_ROOT / reference).is_file() for reference in references)
