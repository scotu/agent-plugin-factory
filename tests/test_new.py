import tempfile
import unittest
from pathlib import Path

from factory import config, upstream
from factory.gitutil import git
from tests.helpers import Sandbox


class NewTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.cleanup()

    def test_plugin_folder_and_config(self):
        plugin = config.load(self.sb.root, "demo")
        self.assertEqual(plugin.repo, self.sb.upstream.as_uri())
        self.assertEqual(plugin.path, "plug")
        self.assertEqual(plugin.targets["hermes"].build_repo, self.sb.remote.as_uri())
        self.assertTrue((plugin.dir / "hermes" / "port.py").exists())

    def test_build_repo_branches_pushed(self):
        self.assertEqual(git(self.sb.remote, "log", "--format=%s", "refs/heads/upstream"), "init")
        self.assertIn("C-000", git(self.sb.remote, "log", "-1", "--format=%s", "refs/heads/main"))
        ledger = git(self.sb.remote, "show", "refs/heads/main:CUSTOMIZATIONS.md")
        self.assertIn("# demo customizations", ledger)
        self.assertNotIn("{{", ledger)

    def test_refuses_existing_plugin(self):
        with self.assertRaisesRegex(config.ConfigError, "already exists"):
            from factory.new import new
            new(self.sb.root, "demo", "hermes", "x#y", self.sb.remote.as_uri())

    def test_fetch_checks_out_only_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "u"
            sha = upstream.fetch(self.sb.upstream.as_uri(), "plug", "main", dest)
            self.assertEqual(sha, git(self.sb.upstream, "rev-parse", "HEAD"))
            self.assertTrue((dest / "plug" / "a.txt").exists())
            self.assertFalse((dest / "other").exists())

    def test_count_ahead(self):
        first = git(self.sb.upstream, "rev-parse", "HEAD")
        self.sb.write_upstream("b.txt", "b\n")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(upstream.count_ahead(self.sb.upstream.as_uri(), "plug", "main", first,
                                                  Path(tmp) / "u"), 1)


if __name__ == "__main__":
    unittest.main()
