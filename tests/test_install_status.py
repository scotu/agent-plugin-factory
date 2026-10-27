import json
import unittest

from factory import build, install, status
from tests.helpers import Sandbox


def fake_install(sb, profile, key, source, revision="abc1234def"):
    meta = sb.profiles / profile / "plugins" / ".install-metadata.json"
    meta.parent.mkdir(parents=True)
    meta.write_text(json.dumps({key: {"pinned": False, "revision": revision, "source": source}}))


class InstallStatusTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        build.sync(self.sb.root, "demo", "hermes")

    def tearDown(self):
        self.sb.cleanup()

    def test_installed_matches_only_this_clone(self):
        fake_install(self.sb, "alpha", "demo", self.sb.clone.as_uri())
        fake_install(self.sb, "beta", "demo", "file:///elsewhere/demo")
        fake_install(self.sb, "gamma", "other", self.sb.clone.as_uri())
        self.assertEqual(install.installed(self.sb.profiles, "demo", self.sb.clone), [("alpha", "abc1234def")])

    def test_status_line(self):
        fake_install(self.sb, "alpha", "demo", self.sb.clone.as_uri())
        (line,) = status.lines(self.sb.root, ["demo"], self.sb.profiles)
        self.assertTrue(line.startswith("demo/hermes: "))
        self.assertIn("0 new upstream commits on main", line)
        self.assertIn("0 active customizations", line)
        self.assertIn("installed: alpha@abc1234", line)
        self.sb.write_upstream("b.txt", "bee\n")
        (line,) = status.lines(self.sb.root, ["demo"], self.sb.profiles)
        self.assertIn("1 new upstream commits on main", line)

    def test_claude_code_installed_reads_commit(self):
        plugins_json = self.sb.profiles.parent / "installed_plugins.json"
        self.assertEqual(install.claude_code_installed(plugins_json, "pstack@mk"), [])
        plugins_json.write_text(json.dumps({"version": 2, "plugins": {
            "pstack@mk": [{"scope": "user", "gitCommitSha": "abc1234def"}]}}))
        self.assertEqual(install.claude_code_installed(plugins_json, "pstack@mk"), [("user", "abc1234def")])

    def test_claude_code_install_without_record_found_in_cache(self):
        import os, time
        root = self.sb.profiles.parent / "cc-plugins"
        cache = root / "cache" / "mk" / "pstack"
        (cache / "aaaaaaaaaaaa").mkdir(parents=True)
        (cache / "bbbbbbbbbbbb").mkdir()
        os.utime(cache / "aaaaaaaaaaaa", (time.time() - 100, time.time() - 100))
        (cache / "cccccccccccc").mkdir()
        (cache / "cccccccccccc" / ".orphaned_at").write_text("1")
        plugins_json = root / "installed_plugins.json"
        plugins_json.write_text(json.dumps({"version": 2, "plugins": {}}))
        self.assertEqual(install.claude_code_installed(plugins_json, "pstack@mk"), [("cache", "bbbbbbbbbbbb")])

    def test_claude_code_malformed_record_is_ignored(self):
        plugins_json = self.sb.profiles.parent / "installed_plugins.json"
        plugins_json.write_text("{not json")
        self.assertEqual(install.claude_code_installed(plugins_json, "pstack@mk"), [])

    def test_status_line_claude_code(self):
        toml = self.sb.root / "plugins" / "demo" / "plugin.toml"
        toml.write_text(toml.read_text().replace('plugin_key = "demo"', 'plugin_key = "demo"\nmarketplace = "mk"'))
        plugins_json = self.sb.profiles.parent / "installed_plugins.json"
        plugins_json.write_text(json.dumps({"version": 2, "plugins": {
            "demo@mk": [{"scope": "user", "gitCommitSha": "abc1234def"}]}}))
        (line,) = status.lines(self.sb.root, ["demo"], self.sb.profiles, plugins_json)
        self.assertIn("installed: user@abc1234", line)

    def test_status_not_cloned(self):
        import shutil
        shutil.rmtree(self.sb.clone)
        self.assertEqual(status.lines(self.sb.root, ["demo"], self.sb.profiles), ["demo/hermes: not cloned (run sync)"])


if __name__ == "__main__":
    unittest.main()
