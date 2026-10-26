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
     to it follow.
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


def port(src, out, ctx):
    shutil.copytree(src, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns("node_modules", ".DS_Store"))
    if (out / "README.md").exists():
        (out / "README.md").rename(out / "UPSTREAM-README.md")
    manifest = _manifest(out / ".claude-plugin" / "plugin.json", ctx)
    if (out / "plugin.json").exists():
        _manifest(out / "plugin.json", ctx)
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
