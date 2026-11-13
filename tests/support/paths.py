"""Repository resources shared by development and packaged portable tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = ROOT / "tests"
FIXTURES_ROOT = TESTS_ROOT / "fixtures"
