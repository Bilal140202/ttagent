"""Import the single-file tool as a module for tests.

`ttagent.py` at the repo root is the single source of truth; tests load it
directly by path so the suite exercises the exact file users run.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "ttagent.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("ttagent_tool", SOURCE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("ttagent_tool", mod)
    spec.loader.exec_module(mod)
    return mod


tool = load_tool()
