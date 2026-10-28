"""Text checks for the pstack-on-hermes overlay's mappings."""
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "plugins" / "pstack" / "hermes" / "overlay" / "skills" / "pstack-on-hermes" / "SKILL.md"


class OnHermesMappingTest(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text()

    def test_orchestrate_tracking_is_mapped(self):
        self.assertIn("Project tracker (`notes.md`)", self.text)
        self.assertIn("PR and CI event subscriptions", self.text)

    def test_plugin_cache_is_mapped(self):
        self.assertIn("`plugins/cache/`", self.text)

    def test_inline_media_is_mapped(self):
        self.assertIn("Embedding a screenshot or video", self.text)

    def test_other_harness_installs_are_mapped(self):
        self.assertIn("Install steps for Cursor or Claude Code", self.text)

    def test_scripts_list_matches_the_tree(self):
        scripts = self.text.split("## Scripts\n", 1)[1]
        self.assertNotIn("`orch`", scripts)
        self.assertIn("statechart", scripts)


if __name__ == "__main__":
    unittest.main()
