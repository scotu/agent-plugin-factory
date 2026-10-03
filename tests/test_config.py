import tempfile
import unittest
from pathlib import Path

from factory.config import ConfigError, Target, load, names

TOML = """
[upstream]
repo = "https://example.com/up.git"
path = "plug"
ref = "main"

[targets.hermes]
build_repo = "git@github.com:me/demo-hermes.git"
plugin_key = "demo"
"""


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "plugins" / "demo").mkdir(parents=True)
        (self.root / "plugins" / "demo" / "plugin.toml").write_text(TOML)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load(self):
        plugin = load(self.root, "demo")
        self.assertEqual((plugin.repo, plugin.path, plugin.ref), ("https://example.com/up.git", "plug", "main"))
        self.assertEqual(plugin.dir, self.root / "plugins" / "demo")
        self.assertEqual(plugin.targets, {"hermes": Target("hermes", "git@github.com:me/demo-hermes.git", "demo")})

    def test_defaults(self):
        (self.root / "plugins" / "demo" / "plugin.toml").write_text(
            '[upstream]\nrepo = "u"\n[targets.hermes]\nbuild_repo = "b"\n')
        plugin = load(self.root, "demo")
        self.assertEqual((plugin.path, plugin.ref, plugin.targets["hermes"].plugin_key), ("", "main", "demo"))

    def test_unknown_plugin(self):
        with self.assertRaisesRegex(ConfigError, "unknown plugin 'nope'"):
            load(self.root, "nope")

    def test_missing_key(self):
        (self.root / "plugins" / "demo" / "plugin.toml").write_text('[upstream]\nrepo = "u"\n')
        with self.assertRaisesRegex(ConfigError, "targets"):
            load(self.root, "demo")

    def test_names(self):
        (self.root / "plugins" / "empty").mkdir()
        self.assertEqual(names(self.root), ["demo"])


if __name__ == "__main__":
    unittest.main()
