"""The pstack Claude Code port hook, run on a small fixture tree shaped like upstream's harness/pstack/claude-code."""
import json
import tempfile
import unittest
from pathlib import Path

from factory.build import Context, load_hook

HERE = Path(__file__).resolve().parent.parent / "plugins" / "pstack" / "claude-code"
SHA = "a" * 40


class PortTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.src, self.out = base / "src", base / "out"
        (self.src / ".claude-plugin").mkdir(parents=True)
        (self.src / ".claude-plugin" / "plugin.json").write_text(json.dumps(
            {"name": "pstack", "version": "9.9.9", "description": "upstream words"}))
        (self.src / "plugin.json").write_text(json.dumps({"name": "pstack", "version": "9.9.9", "description": "upstream words"}))
        (self.src / "skills" / "a").mkdir(parents=True)
        (self.src / "skills" / "a" / "SKILL.md").write_text(
            "---\nname: a\n---\n[g](../../docs/guide/gone.md) [n](../../docs/guide/nowhere.md) "
            "[m](https://github.com/cursor/plugins/blob/main/pstack/skills/a/SKILL.md)\n")
        (self.src / "docs" / "harness").mkdir(parents=True)
        (self.src / "docs" / "harness" / "claude-code.md").write_text("# pstack in Claude Code\n\nupstream adapter\n")
        self.out.mkdir()
        self.ctx = Context("pstack", "claude-code", HERE, SHA, "main")

    def tearDown(self):
        self._tmp.cleanup()

    def run_port(self, drop_guide=True):
        if not drop_guide:
            (self.src / "docs" / "guide").mkdir()
            (self.src / "docs" / "guide" / "gone.md").write_text("guide\n")
        load_hook(HERE)(self.src, self.out, self.ctx)
        return json.loads((self.out / ".claude-plugin" / "plugin.json").read_text())

    def test_manifest_has_no_version_and_names_upstream(self):
        manifest = self.run_port()
        self.assertNotIn("version", manifest)
        self.assertIn("(pstack 9.9.9, upstream aaaaaaa)", manifest["description"])
        self.assertNotIn("version", json.loads((self.out / "plugin.json").read_text()))
        self.assertEqual(self.ctx.version, "9.9.9")

    def test_marketplace_lists_pstack_at_root(self):
        manifest = self.run_port()
        market = json.loads((self.out / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(market["name"], "scotu-pstack")
        self.assertEqual(market["plugins"], [{"name": "pstack", "source": "./", "description": manifest["description"]}])

    def test_adapter_gets_codex_section(self):
        self.run_port()
        text = (self.out / "docs" / "harness" / "claude-code.md").read_text()
        self.assertTrue(text.startswith("# pstack in Claude Code\n\nupstream adapter\n"))
        self.assertIn("## Codex", text)

    def test_overlay_skill_present(self):
        self.run_port()
        self.assertIn("name: pstack-codex", (self.out / "skills" / "pstack-codex" / "SKILL.md").read_text())

    def test_dropped_link_pinned(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cc_port", HERE / "port.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        (self.src / "docs" / "guide").mkdir()
        (self.src / "docs" / "guide" / "gone.md").write_text("guide\n")
        (self.out / "skills" / "a").mkdir(parents=True)
        (self.out / "skills" / "a" / "SKILL.md").write_text((self.src / "skills" / "a" / "SKILL.md").read_text())
        mod.relink(self.out, self.src, SHA)
        text = (self.out / "skills" / "a" / "SKILL.md").read_text()
        self.assertIn(f"(https://github.com/cursor/plugins/blob/{SHA}/harness/pstack/claude-code/docs/guide/gone.md)", text)
        self.assertIn("(../../docs/guide/nowhere.md)", text)
        self.assertIn(f"(https://github.com/cursor/plugins/blob/{SHA}/pstack/skills/a/SKILL.md)", text)

if __name__ == "__main__":
    unittest.main()
