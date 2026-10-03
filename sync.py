#!/usr/bin/env python3
"""Build a Hermes-loadable pstack from upstream cursor/plugins, then merge it into our fork.

Usage: sync.py [git-ref] [--install]        (default ref: main)

Upstream skill text is copied verbatim except for three mechanical edits:
  1. each SKILL.md `name:` is set to its directory name (Hermes requires it),
  2. a one-line pointer to the `pstack-on-hermes` skill is inserted after the
     frontmatter,
  3. skills in EXCLUDE are dropped and overlay/skills/* are added or replace upstream.
The result is committed to the `upstream` branch of build/pstack/ and merged into `main`.
build/pstack/ is its own git repo, cloned from BUILD_REMOTE on first run and pushed back after
every successful merge. `main` which carries the personal changes listed in CUSTOMIZATIONS.md and is
what `hermes plugins install file://...` installs. `main` is only ever merged into, never
rewritten: `hermes plugins update` pulls with --ff-only.
--install runs `hermes -p <profile> plugins update pstack` for every profile installed from here.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

UPSTREAM = "https://github.com/cursor/plugins"
BUILD_REMOTE = "git@github.com:scotu/pstack-hermes-build.git"
HERE = Path(__file__).resolve().parent
OUT = HERE / "build" / "pstack"
LEDGER = OUT / "CUSTOMIZATIONS.md"
PROFILES = Path.home() / ".hermes" / "profiles"
OVERLAY = HERE / "overlay" / "skills"
# setup-pstack is replaced by the overlay; make-bot-ui is platform-specific
# (dr-eggbot ships its own Hermes version).
EXCLUDE = {"make-bot-ui"}
PLUGIN_KEY = "pstack"
# Hermes namespaces portable-plugin skills as agent-plugin-<slug>-<sha256(key)[:8]>
# (hermes_cli/plugins_manifest.py::_portable_skill_namespace); bare names do not resolve.
NS = f"agent-plugin-{PLUGIN_KEY}-{hashlib.sha256(PLUGIN_KEY.encode()).hexdigest()[:8]}"
POINTER = (f"> **On Hermes:** load `{NS}:pstack-on-hermes` with `skill_view` first and apply its "
           "substitutions (subagents, models, paths, missing Cursor features).\n\n")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def run(*cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def git(*args, check=True):
    return subprocess.run(("git", *args), cwd=OUT, check=check, capture_output=True, text=True)


def has_branch(name):
    return git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False).returncode == 0


def checkout_upstream():
    """Put build/pstack on the `upstream` branch, up to date with BUILD_REMOTE (cloned on first run)."""
    if not (OUT / ".git").exists():
        run("git", "clone", "-q", BUILD_REMOTE, str(OUT))
    git("config", "rerere.enabled", "true")
    if git("status", "--porcelain").stdout.strip():
        raise SystemExit(f"{OUT} has uncommitted changes or an unfinished merge; commit or resolve them first.")
    git("fetch", "-q", "origin")
    if not has_branch("upstream"):
        git("branch", "upstream", "refs/remotes/origin/upstream")
    git("checkout", "-q", "upstream")
    git("merge", "-q", "--ff-only", "refs/remotes/origin/upstream")
    return git("rev-parse", "HEAD").stdout.strip()


def touched_entries(old, new):
    """Active ledger entries whose Touches files changed upstream between old and new."""
    if not old or old == new or not LEDGER.exists():
        return []
    changed = set(git("diff", "--name-only", old, new).stdout.split())
    hits = []
    for entry in re.split(r"^(?=## C-)", LEDGER.read_text(), flags=re.M)[1:]:
        title = entry.splitlines()[0][3:]
        touches = re.search(r"^Touches:(.*)$", entry, re.M)
        if "[active]" in title and touches:
            paths = {t.strip() for t in touches.group(1).split(",") if t.strip()}
            if any(c == p or c.startswith(p.rstrip("/") + "/") for p in paths for c in changed):
                hits.append(title)
    return hits


def merge_into_main(old_upstream, version, sha):
    git("checkout", "-q", "main")
    git("merge", "-q", "--ff-only", "refs/remotes/origin/main")
    new_upstream = git("rev-parse", "refs/heads/upstream").stdout.strip()
    for title in touched_entries(old_upstream, new_upstream):
        print(f"review (upstream touched its files): {title}")
    merge = git("merge", "--no-ff", "-q", "refs/heads/upstream", "-m", f"merge upstream pstack {version} @ {sha[:12]}",
                check=False)
    if merge.returncode:
        conflicts = git("diff", "--name-only", "--diff-filter=U").stdout.split()
        print("MERGE CONFLICT on main. Re-apply each affected entry's Intent from", LEDGER)
        print("\n".join(f"  {c}" for c in conflicts) or merge.stdout + merge.stderr)
        print("then `git -C build/pstack commit --no-edit` and re-run (it pushes, and installs with --install).")
        raise SystemExit(1)
    git("push", "-q", "origin", "main", "upstream")


def install():
    for meta in sorted(PROFILES.glob("*/plugins/.install-metadata.json")):
        entry = json.loads(meta.read_text()).get(PLUGIN_KEY, {})
        if entry.get("source") == OUT.as_uri():
            profile = meta.parents[1].name
            print(f"updating {profile}: ", end="", flush=True)
            out = run("hermes", "-p", profile, "plugins", "update", PLUGIN_KEY).splitlines()
            print(out[-1] if out else "ok")


def fetch(ref, dest):
    run("git", "clone", "-q", "--filter=blob:none", "--sparse", "--no-checkout", UPSTREAM, str(dest))
    run("git", "sparse-checkout", "set", "pstack", cwd=dest)
    run("git", "checkout", "-q", ref, cwd=dest)
    return run("git", "rev-parse", "HEAD", cwd=dest)


def patch_skill(skill_md, pointer):
    text = skill_md.read_text()
    m = FRONTMATTER.match(text)
    if not m:
        raise SystemExit(f"{skill_md}: no frontmatter")
    fm = re.sub(r"^name:.*$", f"name: {skill_md.parent.name}", m.group(1), count=1, flags=re.M)
    body = text[m.end():].lstrip("\n").replace("{{NS}}", NS)
    skill_md.write_text(f"---\n{fm}\n---\n\n{pointer if pointer else ''}{body}")


def main():
    args = [a for a in sys.argv[1:] if a != "--install"]
    ref = args[0] if args else "main"
    with tempfile.TemporaryDirectory() as tmp:
        src_repo = Path(tmp) / "plugins"
        sha = fetch(ref, src_repo)
        src = src_repo / "pstack"
        upstream_manifest = json.loads((src / ".cursor-plugin" / "plugin.json").read_text())

        old_upstream = checkout_upstream()
        for child in OUT.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() else child.unlink()

        skills = OUT / "skills"
        shutil.copytree(src / "skills", skills,
                        ignore=shutil.ignore_patterns("node_modules", ".DS_Store"))
        for name in EXCLUDE:
            shutil.rmtree(skills / name, ignore_errors=True)
        for skill_md in skills.glob("*/SKILL.md"):
            patch_skill(skill_md, POINTER)

        for overlay_skill in OVERLAY.iterdir():
            dest = skills / overlay_skill.name
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(overlay_skill, dest)
            patch_skill(dest / "SKILL.md", None)
        refs = skills / "pstack-on-hermes" / "references"
        refs.mkdir(exist_ok=True)
        for agent in (src / "agents").glob("*.md"):
            shutil.copy2(agent, refs / agent.name)

        shutil.copy2(src / "LICENSE", OUT / "LICENSE")
        shutil.copy2(src / "README.md", OUT / "UPSTREAM-README.md")
        (OUT / "UPSTREAM").write_text(f"repo: {UPSTREAM}\npath: pstack\nref: {ref}\ncommit: {sha}\n")
        (OUT / "plugin.json").write_text(json.dumps({
            "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "name": PLUGIN_KEY,
            "version": f"{upstream_manifest['version']}+hermes.{sha[:7]}",
            "description": upstream_manifest["description"],
            "author": upstream_manifest["author"],
            "homepage": upstream_manifest["homepage"],
            "repository": upstream_manifest["repository"],
            "license": upstream_manifest["license"],
            "keywords": upstream_manifest["keywords"],
        }, indent=2) + "\n")

    run("git", "add", "-A", cwd=OUT)
    if run("git", "status", "--porcelain", cwd=OUT):
        run("git", "-c", "user.name=pstack-hermes-sync", "-c", "user.email=pstack-hermes@localhost",
            "commit", "-q", "-m", f"pstack {upstream_manifest['version']} @ {sha[:12]}", cwd=OUT)
    print(f"built upstream from {ref} ({sha[:12]}), {len(list(skills.glob('*/SKILL.md')))} skills, "
          f"commit {run('git', 'rev-parse', '--short', 'HEAD', cwd=OUT)}")
    merge_into_main(old_upstream, upstream_manifest["version"], sha)
    print(f"main at {run('git', 'rev-parse', '--short', 'HEAD', cwd=OUT)}")
    if "--install" in sys.argv:
        install()


if __name__ == "__main__":
    main()
