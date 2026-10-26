"""Local workbench CLI for humans and code agents. Start serve.py first."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'.cac/tools'))
from scene_completion.workbench_cli import entry
if __name__=='__main__':raise SystemExit(entry())
