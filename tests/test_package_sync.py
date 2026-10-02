"""Drift guard: the package must be a byte-identical copy of the tool."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PackageSyncTests(unittest.TestCase):
    def test_sync_check_passes(self):
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sync_package.py"),
             "--check"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_init_is_byte_identical_to_tool(self):
        src = (ROOT / "ttagent.py").read_bytes()
        pkg = (ROOT / "ttagent" / "__init__.py").read_bytes()
        self.assertEqual(src, pkg,
                         "ttagent/__init__.py drifted from ttagent.py — "
                         "run `python scripts/sync_package.py`")

    def test_main_entry_exposes_main(self):
        src = (ROOT / "ttagent.py").read_text(encoding="utf-8")
        self.assertIn("def main(", src)
        self.assertIn('if __name__ == "__main__":', src)


if __name__ == "__main__":
    unittest.main()
