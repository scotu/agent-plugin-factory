import subprocess
import sys
import unittest
from pathlib import Path

from factory.gitutil import git
from tests.helpers import Sandbox

REPO = Path(__file__).resolve().parent.parent


class CliTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "factory", "--root", str(self.sb.root),
                               "--profiles", str(self.sb.profiles), *args],
                              cwd=REPO, capture_output=True, text=True)

    def test_sync_and_status(self):
        r = self.cli("sync", "demo")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("demo/hermes: upstream", r.stdout)
        self.assertIn("pushed", r.stdout)
        r = self.cli("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("installed: none", r.stdout)

    def test_conflict_exits_1(self):
        self.cli("sync", "demo")
        (self.sb.clone / "a.txt").write_text("one\nmine\nthree\n")
        git(self.sb.clone, "commit", "-qam", "C-001: mine")
        self.sb.write_upstream("a.txt", "one\ntheirs\nthree\n")
        r = self.cli("sync", "demo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MERGE CONFLICT", r.stdout)
        self.assertIn("a.txt", r.stdout)

    def test_cli_unknown_plugin_exits_1(self):
        r = self.cli("sync", "nope")
        self.assertEqual(r.returncode, 1)
        self.assertIn("error: unknown plugin 'nope'", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_new_with_explicit_remote(self):
        remote = self.sb.root.parent / "two.git"
        remote.mkdir()
        git(remote, "init", "-q", "--bare", "-b", "main")
        r = self.cli("new", "two", "--upstream", f"{self.sb.upstream.as_uri()}#plug", "--remote", remote.as_uri())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.sb.root / "plugins" / "two" / "hermes" / "port.py").exists())


if __name__ == "__main__":
    unittest.main()
