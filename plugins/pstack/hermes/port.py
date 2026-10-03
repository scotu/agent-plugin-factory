"""Port upstream pstack (Cursor plugin) to a Hermes portable plugin (Agent Plugins v1).

Upstream skill text is copied verbatim except for three mechanical edits:
  1. each SKILL.md `name:` is set to its directory name (Hermes requires it),
  2. a one-line pointer to the `pstack-on-hermes` skill is inserted after the frontmatter,
  3. skills in EXCLUDE are dropped and overlay/skills/* are added or replace upstream.
"""
import hashlib
import json
import re
import shutil

PLUGIN_KEY = "pstack"
# setup-pstack is replaced by the overlay; make-bot-ui is platform-specific
# (dr-eggbot ships its own Hermes version).
EXCLUDE = {"make-bot-ui"}
# Hermes namespaces portable-plugin skills as agent-plugin-<slug>-<sha256(key)[:8]>
# (hermes_cli/plugins_manifest.py::_portable_skill_namespace); bare names do not resolve.
NS = f"agent-plugin-{PLUGIN_KEY}-{hashlib.sha256(PLUGIN_KEY.encode()).hexdigest()[:8]}"
POINTER = (f"> **On Hermes:** load `{NS}:pstack-on-hermes` with `skill_view` first and apply its "
           "substitutions (subagents, models, paths, missing Cursor features).\n\n")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def patch_skill(skill_md, pointer):
    text = skill_md.read_text()
    m = FRONTMATTER.match(text)
    if not m:
        raise SystemExit(f"{skill_md}: no frontmatter")
    fm = re.sub(r"^name:.*$", f"name: {skill_md.parent.name}", m.group(1), count=1, flags=re.M)
    body = text[m.end():].lstrip("\n").replace("{{NS}}", NS)
    skill_md.write_text(f"---\n{fm}\n---\n\n{pointer if pointer else ''}{body}")


def port(src, out, ctx):
    upstream_manifest = json.loads((src / ".cursor-plugin" / "plugin.json").read_text())
    ctx.version = upstream_manifest["version"]

    skills = out / "skills"
    shutil.copytree(src / "skills", skills, ignore=shutil.ignore_patterns("node_modules", ".DS_Store"))
    for name in EXCLUDE:
        shutil.rmtree(skills / name, ignore_errors=True)
    for skill_md in skills.glob("*/SKILL.md"):
        patch_skill(skill_md, POINTER)

    for overlay_skill in (ctx.here / "overlay" / "skills").iterdir():
        if not overlay_skill.is_dir():
            continue
        dest = skills / overlay_skill.name
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(overlay_skill, dest)
        patch_skill(dest / "SKILL.md", None)
    refs = skills / "pstack-on-hermes" / "references"
    refs.mkdir(exist_ok=True)
    for agent in (src / "agents").glob("*.md"):
        shutil.copy2(agent, refs / agent.name)

    shutil.copy2(src / "LICENSE", out / "LICENSE")
    shutil.copy2(src / "README.md", out / "UPSTREAM-README.md")
    (out / "plugin.json").write_text(json.dumps({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": PLUGIN_KEY,
        "version": f"{upstream_manifest['version']}+hermes.{ctx.upstream_sha[:7]}",
        "description": upstream_manifest["description"],
        "author": upstream_manifest["author"],
        "homepage": upstream_manifest["homepage"],
        "repository": upstream_manifest["repository"],
        "license": upstream_manifest["license"],
        "keywords": upstream_manifest["keywords"],
    }, indent=2) + "\n")
