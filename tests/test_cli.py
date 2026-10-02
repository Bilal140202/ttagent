"""CLI subprocess contract: exit codes, --json stdout purity, summary keys."""
import json
import subprocess
import sys
import unittest

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
TOOL = ROOT / "ttagent.py"


def run_cli(*args):
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True, timeout=120)


class CliContractTests(unittest.TestCase):
    def test_version(self):
        p = run_cli("--version")
        self.assertEqual(p.returncode, 0)
        self.assertIn("ttagent", p.stdout)

    def test_invalid_input_exit2_json(self):
        p = run_cli("not a real thing!!", "--json", "--quiet")
        self.assertEqual(p.returncode, 2)
        data = json.loads(p.stdout)
        self.assertFalse(data["ok"])
        self.assertEqual(data["status"], "invalid_input")
        self.assertEqual(data["error"]["code"], "E_INVALID_INPUT")

    def test_unsupported_profile_url_exit2(self):
        p = run_cli("https://www.tiktok.com/@someuser/", "--json", "--quiet")
        self.assertEqual(p.returncode, 2)
        data = json.loads(p.stdout)
        self.assertEqual(data["status"], "invalid_input")

    def test_json_single_object_on_offline_path(self):
        p = run_cli("https://www.tiktok.com/@someuser/", "--json", "--quiet")
        lines = [ln for ln in p.stdout.strip().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        for key in ("ok", "status", "error"):
            self.assertIn(key, data)

    def test_no_traceback_leak_on_bad_input(self):
        p = run_cli("!!!")
        self.assertNotIn("Traceback", p.stderr)
        self.assertNotIn("Traceback", p.stdout)


if __name__ == "__main__":
    unittest.main()
