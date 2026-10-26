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

    def _remote2(self):
        remote = self.sb.root.parent / "two-cc.git"
        remote.mkdir()
        git(remote, "init", "-q", "--bare", "-b", "main")
        return remote

    def test_add_target_to_existing_plugin(self):
        from factory.new import add_target
        remote = self._remote2()
        port = self.sb.root / "plugins" / "demo" / "hermes" / "port.py"
        before = port.read_text()
        add_target(self.sb.root, "demo", "cc", remote.as_uri(), path="plug2", marketplace="mk")
        target = config.load(self.sb.root, "demo").targets["cc"]
        self.assertEqual((target.path, target.marketplace, target.plugin_key), ("plug2", "mk", "demo"))
        self.assertEqual(git(remote, "log", "--format=%s", "refs/heads/upstream"), "init")
        self.assertIn("C-000", git(remote, "log", "-1", "--format=%s", "refs/heads/main"))
        self.assertTrue((self.sb.root / "plugins" / "demo" / "cc" / "port.py").exists())
        self.assertEqual(port.read_text(), before)

    def test_add_target_refuses_existing_target(self):
        from factory.new import add_target
        with self.assertRaisesRegex(config.ConfigError, "already has target"):
            add_target(self.sb.root, "demo", "hermes", self._remote2().as_uri())

    def test_refuses_existing_plugin(self):
        with self.assertRaisesRegex(config.ConfigError, "already exists"):
            from factory.new import new
            new(self.sb.root, "demo", "hermes", "x#y", self.sb.remote.as_uri())

    def test_failed_push_leaves_nothing_behind_and_can_be_rerun(self):
        from factory.gitutil import GitError
        from factory.new import clone_path, new
        bad = (self.sb.root.parent / "missing.git").as_uri()
        with self.assertRaises(GitError):
            new(self.sb.root, "two", "hermes", "x#y", bad)
        self.assertFalse((self.sb.root / "plugins" / "two").exists())
        self.assertFalse(clone_path(self.sb.root, "two", "hermes").exists())
        good = self.sb.root.parent / "two.git"
        good.mkdir()
        git(good, "init", "-q", "--bare", "-b", "main")
        new(self.sb.root, "two", "hermes", "x#y", good.as_uri())
        self.assertTrue((self.sb.root / "plugins" / "two" / "plugin.toml").exists())

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
