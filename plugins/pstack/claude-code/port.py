"""Port upstream pstack's Claude Code tree (cursor/plugins harness/pstack/claude-code) into a Claude Code
marketplace repo.

The upstream tree is already a Claude Code plugin, so the port is a copy plus four mechanical edits:
  1. the manifests drop `version`, so Claude Code versions each install by commit, and the upstream version moves
     into the description,
  2. `.claude-plugin/marketplace.json` makes the build repo a one-plugin marketplace,
  3. overlay/skills/* are added, and overlay/adapter-more.md (Cursor names upstream's adapter leaves out) and
     overlay/adapter-codex.md are appended to the Claude Code adapter,
  4. relative links to files outside the tree point at upstream on GitHub pinned to the built commit, and links
     upstream already points at `main` are pinned too,
  5. upstream's README.md ships as UPSTREAM-README.md (the build repo's own README.md lives on `main`), and links
     to it follow,
  6. every SKILL.md gets upstream's one-line adapter pointer if it lacks one, agents/poteto-agent.md learns its
     Claude Code path, the human-facing guide pages and UPSTREAM-README.md get a fork banner, worktree-audit.sh reads
     Claude Code transcripts, and EXCLUDE plus the root plugin.json (which Claude Code ignores) are dropped.
"""
import json
import os
import re
import shutil

MARKETPLACE = "scotu-pstack"
ADAPTER = "docs/harness/claude-code.md"
UPSTREAM_BLOB = "https://github.com/cursor/plugins/blob/{sha}/harness/pstack/claude-code/{path}"
MAIN_BLOB = re.compile(r"https://github\.com/cursor/plugins/blob/main/")
LINK = re.compile(r"\]\(([^)\s#:]+)(#[^)]*)?\)")
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
# make-bot-ui drives Cursor Automations (routines, webhooks), which Claude Code doesn't have.
EXCLUDE = {"make-bot-ui"}
POINTER = ("In Claude Code, read [the Claude Code adapter](../../docs/harness/claude-code.md) once per session before "
           "you follow this skill. It maps the Cursor names in pstack skills to Claude Code.\n\n")
AGENT_PATH = ("> **In Claude Code:** poteto-mode is at `${CLAUDE_PLUGIN_ROOT}/skills/poteto-mode/SKILL.md`. That is "
              "the path to read; never search `~/.cursor/plugins/`.\n\n")
BANNER = ("> **This is scotu/pstack-claude-code**, pstack built for Claude Code. Install it with "
          "`claude plugin marketplace add scotu/pstack-claude-code` and `claude plugin install pstack@scotu-pstack`. "
          "It runs lean by default (`skills/pstack-economy`): the panel and lane widths described here are the "
          "go-wide forms, used when you approve them for a task. Cursor-only features map to Claude Code through "
          "`docs/harness/claude-code.md`.\n\n")
TRANSCRIPTS = (
    "slug=$(printf '%s' \"$main_wt\" | sed 's#^/##; s#/#-#g')\n"
    'transcripts="$HOME/.cursor/projects/$slug/agent-transcripts"',
    "slug=$(printf '%s' \"$main_wt\" | sed 's#[/.]#-#g')\n"
    'transcripts="$HOME/.claude/projects/$slug"',
)


def relink(out, src, sha):
    for md in out.rglob("*.md"):
        text = md.read_text()

        def fix(m):
            target, anchor = m.group(1), m.group(2) or ""
            if (md.parent / target).exists():
                return m.group(0)
            rel = os.path.normpath(os.path.join(os.path.relpath(md.parent, out), target))
            if rel == "README.md":
                return f"]({os.path.relpath(out / 'UPSTREAM-README.md', md.parent)}{anchor})"
            if (src / rel).exists():
                return f"]({UPSTREAM_BLOB.format(sha=sha, path=rel)}{anchor})"
            return m.group(0)  # dangling upstream too: left for tests/test_principles.py to flag

        new = MAIN_BLOB.sub(f"https://github.com/cursor/plugins/blob/{sha}/", LINK.sub(fix, text))
        if new != text:
            md.write_text(new)


def _manifest(path, ctx):
    data = json.loads(path.read_text())
    version = data.pop("version", None)
    if version:
        ctx.version = version
    data["description"] = f"{data.get('description', '').rstrip()} (pstack {ctx.version}, upstream {ctx.upstream_sha[:7]})".lstrip()
    path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def _after_frontmatter(path, text):
    body = path.read_text()
    m = FRONTMATTER.match(body)
    end = m.end() if m else 0
    path.write_text(body[:end] + ("\n" if m else "") + text + body[end:].lstrip("\n"))


def port(src, out, ctx):
    shutil.copytree(src, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns("node_modules", ".DS_Store"))
    for name in EXCLUDE:
        shutil.rmtree(out / "skills" / name, ignore_errors=True)
    (out / "plugin.json").unlink(missing_ok=True)
    if (out / "README.md").exists():
        (out / "README.md").rename(out / "UPSTREAM-README.md")
    manifest = _manifest(out / ".claude-plugin" / "plugin.json", ctx)

    for skill_md in (out / "skills").glob("*/SKILL.md"):
        if "docs/harness/claude-code.md" not in skill_md.read_text():
            _after_frontmatter(skill_md, POINTER)
    agent = out / "agents" / "poteto-agent.md"
    if agent.exists():
        _after_frontmatter(agent, AGENT_PATH)
    for page in [*sorted((out / "docs" / "guide").glob("*.md")), out / "UPSTREAM-README.md"]:
        if page.exists():
            page.write_text(BANNER + page.read_text())
    audit = out / "skills" / "poteto-mode" / "scripts" / "worktree-audit.sh"
    if audit.exists():
        text = audit.read_text()
        if TRANSCRIPTS[0] not in text:
            raise RuntimeError("worktree-audit.sh no longer has the Cursor transcripts lookup; update TRANSCRIPTS")
        audit.write_text(text.replace(TRANSCRIPTS[0], TRANSCRIPTS[1]))
    (out / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
        "name": MARKETPLACE,
        "owner": {"name": "scotu"},
        "plugins": [{"name": "pstack", "source": "./", "description": manifest["description"]}],
    }, indent=2) + "\n")

    for skill in (ctx.here / "overlay" / "skills").iterdir():
        if skill.is_dir():
            shutil.rmtree(out / "skills" / skill.name, ignore_errors=True)
            shutil.copytree(skill, out / "skills" / skill.name)
    adapter = out / ADAPTER
    extra = "\n".join((ctx.here / "overlay" / name).read_text() for name in ("adapter-more.md", "adapter-codex.md"))
    adapter.write_text(adapter.read_text().rstrip("\n") + "\n\n" + extra)

    relink(out, src, ctx.upstream_sha)
