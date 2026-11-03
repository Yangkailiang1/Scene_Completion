"""Resolve installed program resources independently of the working directory."""

from pathlib import Path

PROGRAM_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROGRAM_ROOT / "src"
SKILLS_ROOT = PROGRAM_ROOT / ".cac" / "skills"
AGENTS_ROOT = PROGRAM_ROOT / ".cac" / "agents"
PROMPTS_ROOT = PROGRAM_ROOT / "src" / "scene_completion" / "domain" / "prompts"


def skill_file(name: str) -> Path:
    return SKILLS_ROOT / name / "SKILL.md"
