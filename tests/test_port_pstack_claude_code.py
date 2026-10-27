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

    def test_adapter_maps_names_upstream_leaves_out(self):
        self.run_port()
        text = (self.out / "docs" / "harness" / "claude-code.md").read_text()
        self.assertIn("## More Cursor names", text)
        for name in ("`cursor-team-kit`", "`deslop`", "`control-ui`", "`control-cli`", "`/create-skill`", "`/loop`",
                     "`/visualize`", "`/orchestrate`"):
            self.assertIn(name, text)
        self.assertLess(text.index("## More Cursor names"), text.index("## Codex"))

    def test_overlay_skill_present(self):
        self.run_port()
        self.assertIn("name: pstack-codex", (self.out / "skills" / "pstack-codex" / "SKILL.md").read_text())

    def test_upstream_readme_ships_as_upstream_readme(self):
        (self.src / "README.md").write_text("upstream readme\n")
        (self.src / "skills" / "a" / "SKILL.md").write_text("---\nname: a\n---\n[r](../../README.md#install)\n")
        self.run_port()
        self.assertFalse((self.out / "README.md").exists())
        self.assertTrue((self.out / "UPSTREAM-README.md").read_text().endswith("upstream readme\n"))
        self.assertIn("(../../UPSTREAM-README.md#install)", (self.out / "skills" / "a" / "SKILL.md").read_text())

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


AUDIT_SH = """# Transcripts dir: ~/.cursor/projects/<slugified-repo-path>/agent-transcripts.
slug=$(printf '%s' "$main_wt" | sed 's#^/##; s#/#-#g')
transcripts="$HOME/.cursor/projects/$slug/agent-transcripts"
"""


class PortTreeTest(PortTest):
    """Port edits on the parts of the tree that the base fixture doesn't have."""

    def add(self, rel, text):
        path = self.src / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_every_skill_gets_adapter_pointer_once(self):
        self.add("skills/b/SKILL.md", "---\nname: b\n---\n\n# B\n\nIn Claude Code, read [the Claude Code adapter]"
                 "(../../docs/harness/claude-code.md) once per session before you follow this skill.\n")
        self.run_port()
        a = (self.out / "skills" / "a" / "SKILL.md").read_text()
        self.assertTrue(a.startswith("---\nname: a\n---\n\nIn Claude Code, read [the Claude Code adapter]"
                                     "(../../docs/harness/claude-code.md)"), a)
        self.assertEqual((self.out / "skills" / "b" / "SKILL.md").read_text().count("Claude Code adapter"), 1)

    def test_poteto_agent_gets_its_claude_code_path(self):
        self.add("agents/poteto-agent.md", "---\nname: poteto-agent\n---\n\n# Poteto subagent\n\nsearch `~/.cursor/plugins/`\n")
        self.run_port()
        text = (self.out / "agents" / "poteto-agent.md").read_text()
        self.assertIn("---\n\n> **In Claude Code:** poteto-mode is at `${CLAUDE_PLUGIN_ROOT}/skills/poteto-mode/SKILL.md`", text)
        self.assertLess(text.index("${CLAUDE_PLUGIN_ROOT}"), text.index("~/.cursor/plugins/"))

    def test_make_bot_ui_and_root_manifest_dropped(self):
        self.add("skills/make-bot-ui/SKILL.md", "---\nname: make-bot-ui\n---\n")
        self.run_port()
        self.assertFalse((self.out / "skills" / "make-bot-ui").exists())
        self.assertFalse((self.out / "plugin.json").exists())

    def test_guide_pages_and_upstream_readme_get_fork_banner(self):
        self.add("docs/guide/01-setup.md", "# Setup\n")
        self.add("README.md", "# pstack\n")
        self.run_port()
        for rel in ("docs/guide/01-setup.md", "UPSTREAM-README.md"):
            text = (self.out / rel).read_text()
            self.assertTrue(text.startswith("> **This is scotu/pstack-claude-code"), rel)
            self.assertIn("pstack-economy", text)
            self.assertIn("claude plugin marketplace add scotu/pstack-claude-code", text)

    def test_worktree_audit_reads_claude_transcripts(self):
        self.add("skills/poteto-mode/scripts/worktree-audit.sh", AUDIT_SH)
        self.run_port()
        text = (self.out / "skills" / "poteto-mode" / "scripts" / "worktree-audit.sh").read_text()
        self.assertIn('transcripts="$HOME/.claude/projects/$slug"', text)
        self.assertIn("sed 's#[/.]#-#g'", text)
        self.assertNotIn(".cursor/projects", text.split("\n", 1)[1])

    def test_worktree_audit_patch_fails_loudly_when_upstream_moves(self):
        self.add("skills/poteto-mode/scripts/worktree-audit.sh", "transcripts=elsewhere\n")
        with self.assertRaisesRegex(RuntimeError, "worktree-audit.sh"):
            self.run_port()

    def test_adapter_rows_for_audit_findings(self):
        self.run_port()
        text = (self.out / "docs" / "harness" / "claude-code.md").read_text()
        for name in ("agent's store", "`git show origin/main:pstack/<path>`", "Cursor restart", "cloud VM",
                     "Pinned", "`mcps/`", "image-generation", "inline", "Custom Mode", "Cursor Project",
                     "`/in-cloud`", "`/add-plugin pstack`", "`/make-bot-ui`", "`allow_multiple: true`", "first `type: user` record"):
            self.assertIn(name, text)
        codex = text.split("## Codex", 1)[1]
        self.assertIn("overrides the Models row", codex)
        self.assertIn("inherit-parent", codex)


SKILL = HERE / "overlay" / "skills" / "pstack-codex" / "SKILL.md"


def section(heading: str) -> str:
    text = SKILL.read_text()
    start = text.index(f"## {heading}\n")
    nxt = text.find("\n## ", start + 1)
    return text[start:] if nxt == -1 else text[start:nxt]


class CodexSkillTest(unittest.TestCase):
    def test_sections(self):
        for heading in ("Available", "Advisory seat", "Code-writing owner", "Wrapper loop", "Standing down", "Limits"):
            self.assertIn(f"\n## {heading}\n", SKILL.read_text())

    def test_codex_available_checks(self):
        text = section("Available")
        for needle in ("codex --version", "codex login status", "codex-companion.mjs", "codex exec"):
            self.assertIn(needle, text)

    def test_default_model_means_no_flag(self):
        self.assertIn("`codex default <effort>`", section("Available"))

    def test_codex_fallback_sentence(self):
        text = section("Available")
        self.assertIn("say in one line that", text)
        self.assertIn("Claude", text)

    def test_wrapper_owns_git(self):
        owner = section("Code-writing owner") + section("Wrapper loop")
        for needle in ("workspace-write", "git worktree add", "commits", "push", "gh pr create", "--cwd"):
            self.assertIn(needle, owner)
        self.assertIn("does not commit, push, or reach the network", section("Limits"))

    def test_resume_command_named(self):
        text = section("Wrapper loop")
        self.assertIn("--resume-last", text)
        self.assertIn("codex exec resume <session id>", text)
        self.assertIn('-c sandbox_mode="workspace-write"', text)
        self.assertNotIn("resume --last", text)

    def test_each_round_records_its_job(self):
        self.assertIn("update the `job` column", section("Wrapper loop"))

    def test_fallback_pairs_rely_on_stuck(self):
        self.assertIn("session id", section("Code-writing owner"))
        self.assertIn("STUCK", section("Code-writing owner"))

    def test_advisory_is_read_only(self):
        text = section("Advisory seat")
        self.assertIn("without `--write`", text)
        self.assertIn("-s read-only", text)
