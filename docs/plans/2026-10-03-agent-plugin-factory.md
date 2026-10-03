# Agent Plugin Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the `pstack-hermes` tooling repo into `agent-plugin-factory`. It is a generic tool that builds any upstream agent plugin into its own build repo, keeps personal customizations as merged commits, and installs the result into Hermes. pstack is the first plugin.

**Architecture:** A small stdlib-only Python package, `factory/`, does what every plugin needs:
- fetch upstream
- prepare the build repo: clone, fast-forward, `upstream` branch
- call a port hook supplied by each plugin and target, at `plugins/<plugin>/<target>/port.py`
- stamp `UPSTREAM` and `FACTORY`, commit, merge into `main`, review ledger entries, push
- update the Hermes profiles

Each build repo, `scotu/<plugin>-<target>`, is a standalone installable plugin, cloned locally into the gitignored `builds/<target>/<plugin>/`.

**Tech Stack:** Python 3.11+ standard library (`tomllib`, `unittest`, `subprocess`), git, the `gh` CLI (only for `new` and the repo renames), and the `hermes` CLI (only for installs).

**Spec:** `docs/specs/2026-10-03-agent-plugin-factory-design.md`

## Global Constraints

- Python standard library only. No third-party packages. Run tests with `python3 -m unittest discover -s tests -v` from the repo root.
- Invocation is `python3 -m factory <command>`. The spec's root `factory` executable is dropped: a file named `factory` can't sit next to the `factory/` package folder.
- Build repos are named `<plugin>-<target>`, for example `scotu/pstack-hermes`.
- Each build repo has two branches. `upstream` is the exact build output and is never edited by hand. `main` is `upstream` plus `C-NNN` commits plus `CUSTOMIZATIONS.md`, and Hermes installs it.
- Never rewrite `main` in a build repo, because `hermes plugins update` runs `git pull --ff-only`. Never force-push.
- Use `git switch` (never `git checkout <name>`) and `refs/heads/upstream` (never a bare `upstream` argument) wherever a path could be ambiguous. On macOS the `UPSTREAM` file and the `upstream` branch collide.
- The tool commits as `agent-plugin-factory <agent-plugin-factory@localhost>` via `-c` flags, so it works without any git identity configured.
- The `UPSTREAM` file format stays exactly `repo: …\npath: …\nref: …\ncommit: …\n`. `FACTORY` is `commit: <sha>\n` plus `dirty: true\n` when the factory tree had uncommitted changes, or `commit: unknown\n` outside a git repo.
- Only the `hermes` target exists. Its manifest is `plugin.json`.

## Review Focus

1. **Running sync twice with no upstream change** should create no commits and still exit 0, so a cron or habit run is harmless. Test: `test_rerun_without_changes_is_noop` (Task 4).
2. **Running sync again after resolving a conflict by hand** should push the resolution and not rebuild it away. Test: `test_conflict_then_resolution_pushes` (Task 4).
3. **A merge left half-resolved** (conflicts resolved with `git add` but not committed) must be refused, not built over. Test: `test_unfinished_merge_refused` (Task 4).
4. **The ledger template's own `## C-NNN` example** and retired entries must never produce review notices. Test: `test_template_example_and_retired_entries_ignored` (Task 2).
5. **An unknown plugin name or target** should give a clear error, not a traceback or a half-built repo. Tests: `test_unknown_plugin` (Task 2) and `test_cli_unknown_plugin_exits_1` (Task 6).

---

## File Structure

```
factory/__init__.py           empty package marker
factory/__main__.py           argparse CLI: sync | new | status (Task 6)
factory/gitutil.py            git wrapper with the factory identity (Task 1)
factory/ledger.py             CUSTOMIZATIONS.md parsing, touched entries (Task 2)
factory/config.py             plugin.toml loading (Task 2)
factory/upstream.py           fetch an upstream tree; count new upstream commits (Task 3)
factory/build.py              prepare build repo, run hook, stamp, commit, merge, push (Task 4)
factory/new.py                create plugin folder + build repo (Task 3)
factory/install.py            find and update Hermes profiles installed from a build clone (Task 5)
factory/status.py             status lines (Task 5)
factory/templates/            plugin.toml, port.py, CUSTOMIZATIONS.md, README.md for `new` (Task 3)
plugins/pstack/plugin.toml    pstack upstream + hermes target (Task 7)
plugins/pstack/hermes/port.py pstack hook, moved out of sync.py (Task 7)
plugins/pstack/hermes/overlay/skills/...   moved from overlay/skills (Task 7)
tests/helpers.py              Sandbox: fake upstream, bare remote, factory root (Task 3)
tests/test_*.py
README.md, LICENSE, .gitignore  updated (Task 7)
sync.py, overlay/             removed (Task 7)
```

Tasks 1–7 run in `/Users/matteo/Development/agents/pstack-hermes` (renamed to `agent-plugin-factory` in Task 9).

---

### Task 1: git wrapper

**Files:**
- Create: `factory/__init__.py` (empty), `factory/gitutil.py`, `tests/__init__.py` (empty), `tests/test_gitutil.py`

**Interfaces:**
- Produces:
  - `IDENTITY: tuple[str, ...]`
  - `class GitError(RuntimeError)`
  - `run(repo: Path, *args: str) -> subprocess.CompletedProcess`
  - `git(repo: Path, *args: str) -> str` (stripped stdout; raises `GitError`)
  - `ok(repo: Path, *args: str) -> bool`
  - `has_branch(repo: Path, name: str) -> bool`
  - `is_dirty(repo: Path) -> bool` (true for uncommitted changes, untracked files, or an unfinished merge)

- [ ] **Step 1: Write the failing test** in `tests/test_gitutil.py`:

```python
import tempfile
import unittest
from pathlib import Path

from factory.gitutil import GitError, git, has_branch, is_dirty, ok


class GitUtilTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "f.txt").write_text("x\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "first")

    def tearDown(self):
        self.tmp.cleanup()

    def test_commits_with_factory_identity(self):
        self.assertEqual(git(self.repo, "log", "-1", "--format=%an <%ae>"),
                         "agent-plugin-factory <agent-plugin-factory@localhost>")

    def test_git_raises_with_detail(self):
        with self.assertRaises(GitError) as cm:
            git(self.repo, "rev-parse", "no-such-ref")
        self.assertIn("rev-parse", str(cm.exception))

    def test_ok_and_has_branch(self):
        self.assertTrue(has_branch(self.repo, "main"))
        self.assertFalse(has_branch(self.repo, "upstream"))
        self.assertFalse(ok(self.repo, "rev-parse", "--verify", "--quiet", "nope"))

    def test_is_dirty(self):
        self.assertFalse(is_dirty(self.repo))
        (self.repo / "new.txt").write_text("y\n")
        self.assertTrue(is_dirty(self.repo))

    def test_unfinished_merge_is_dirty_even_when_tree_matches_head(self):
        git(self.repo, "switch", "-q", "-c", "side")
        (self.repo / "f.txt").write_text("side\n")
        git(self.repo, "commit", "-qam", "side")
        git(self.repo, "switch", "-q", "main")
        (self.repo / "f.txt").write_text("main\n")
        git(self.repo, "commit", "-qam", "main")
        self.assertFalse(ok(self.repo, "merge", "side"))
        git(self.repo, "checkout", "--ours", "--", "f.txt")
        git(self.repo, "add", "f.txt")
        self.assertTrue(is_dirty(self.repo))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python3 -m unittest tests.test_gitutil -v`. Expected: `ModuleNotFoundError: No module named 'factory.gitutil'`.

- [ ] **Step 3: Implement** `factory/gitutil.py`:

```python
"""Thin git wrapper. Every call carries the factory's commit identity, so builds look the same on any machine."""
import subprocess
from pathlib import Path

IDENTITY = ("-c", "user.name=agent-plugin-factory", "-c", "user.email=agent-plugin-factory@localhost")


class GitError(RuntimeError):
    pass


def run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *IDENTITY, *args], cwd=repo, capture_output=True, text=True)


def git(repo: Path, *args: str) -> str:
    result = run(repo, *args)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise GitError(f"git {' '.join(args)} failed in {repo}:\n{detail}")
    return result.stdout.strip()


def ok(repo: Path, *args: str) -> bool:
    return run(repo, *args).returncode == 0


def has_branch(repo: Path, name: str) -> bool:
    return ok(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}")


def is_dirty(repo: Path) -> bool:
    """Uncommitted changes, untracked files, or a merge that was started but not committed."""
    return bool(git(repo, "status", "--porcelain")) or ok(repo, "rev-parse", "--verify", "--quiet", "MERGE_HEAD")
```

- [ ] **Step 4: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_gitutil -v`. Expected: 5 tests OK.

- [ ] **Step 5: Commit**

```bash
git add factory/__init__.py factory/gitutil.py tests/__init__.py tests/test_gitutil.py
git commit -m "factory: git wrapper with fixed commit identity"
```

---

### Task 2: ledger and plugin config

**Files:**
- Create: `factory/ledger.py`, `factory/config.py`, `tests/test_ledger.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `ledger.Entry(id: str, title: str, status: str, touches: tuple[str, ...])` (frozen dataclass)
  - `ledger.parse(text: str) -> list[Entry]`
  - `ledger.touched(entries: list[Entry], changed: list[str]) -> list[Entry]` (active entries only; a `Touches` path matches the same file, or anything under it when it is a folder)
  - `config.ConfigError(ValueError)`
  - `config.Target(name: str, build_repo: str, plugin_key: str)`
  - `config.Plugin(name: str, dir: Path, repo: str, path: str, ref: str, targets: dict[str, Target])`
  - `config.load(root: Path, name: str) -> Plugin`
  - `config.names(root: Path) -> list[str]`

- [ ] **Step 1: Write the failing tests.**

`tests/test_ledger.py`:
```python
import unittest

from factory.ledger import Entry, parse, touched

LEDGER = """# x customizations

Entry format:

```
## C-NNN — <skill>: <short title>  [active]
Touches: skills/<name>/SKILL.md
```

## C-001 — bro: shorter  [active]
Intent: shorter
Touches: skills/bro/SKILL.md

## C-002 — poteto-mode: no PRs  [active]
Touches: skills/poteto-mode/, README.md

## C-003 — old thing  [retired]
Touches: skills/bro/SKILL.md
"""


class LedgerTest(unittest.TestCase):
    def test_parse(self):
        entries = parse(LEDGER)
        self.assertEqual([e.id for e in entries], ["C-001", "C-002", "C-003"])
        self.assertEqual(entries[0], Entry("C-001", "C-001 — bro: shorter  [active]", "active",
                                           ("skills/bro/SKILL.md",)))
        self.assertEqual(entries[1].touches, ("skills/poteto-mode/", "README.md"))
        self.assertEqual(entries[2].status, "retired")

    def test_touched_matches_files_and_folders(self):
        hits = touched(parse(LEDGER), ["skills/poteto-mode/playbooks/x.md", "UPSTREAM"])
        self.assertEqual([e.id for e in hits], ["C-002"])
        hits = touched(parse(LEDGER), ["skills/bro/SKILL.md"])
        self.assertEqual([e.id for e in hits], ["C-001"])

    def test_template_example_and_retired_entries_ignored(self):
        hits = touched(parse(LEDGER), ["skills/<name>/SKILL.md", "skills/bro/SKILL.md"])
        self.assertEqual([e.id for e in hits], ["C-001"])

    def test_prefix_is_not_a_folder_match(self):
        self.assertEqual(touched(parse(LEDGER), ["skills/poteto-mode-extra/a.md"]), [])

    def test_empty(self):
        self.assertEqual(parse(""), [])


if __name__ == "__main__":
    unittest.main()
```

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python3 -m unittest tests.test_ledger tests.test_config -v`. Expected: `ModuleNotFoundError` for both.

- [ ] **Step 3: Implement.**

`factory/ledger.py`:
```python
"""CUSTOMIZATIONS.md: one `## C-NNN — title  [status]` section per customization, with a `Touches:` line."""
import re
from dataclasses import dataclass

HEADING = re.compile(r"## (C-\d+)\b.*\[(\w+)\]\s*$")


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    status: str
    touches: tuple[str, ...]


def parse(text: str) -> list[Entry]:
    entries = []
    for block in re.split(r"^(?=## C-)", text, flags=re.M)[1:]:
        first = block.splitlines()[0]
        head = HEADING.match(first)
        if not head:  # e.g. the `## C-NNN` example inside the template's code fence
            continue
        line = re.search(r"^Touches:(.*)$", block, re.M)
        touches = tuple(p.strip() for p in line.group(1).split(",") if p.strip()) if line else ()
        entries.append(Entry(head.group(1), first[3:].strip(), head.group(2), touches))
    return entries


def _hit(path: str, changed: str) -> bool:
    return changed == path or changed.startswith(path.rstrip("/") + "/")


def touched(entries: list[Entry], changed: list[str]) -> list[Entry]:
    """Active entries with a Touches path that one of the changed files matches or lies under."""
    return [e for e in entries
            if e.status == "active" and any(_hit(p, c) for p in e.touches for c in changed)]
```

`factory/config.py`:
```python
"""plugins/<name>/plugin.toml: where a plugin comes from and which targets it is built for."""
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Target:
    name: str
    build_repo: str
    plugin_key: str


@dataclass(frozen=True)
class Plugin:
    name: str
    dir: Path
    repo: str
    path: str
    ref: str
    targets: dict[str, Target]


def load(root: Path, name: str) -> Plugin:
    plugin_dir = root / "plugins" / name
    file = plugin_dir / "plugin.toml"
    if not file.exists():
        raise ConfigError(f"unknown plugin '{name}': {file} not found")
    data = tomllib.loads(file.read_text())
    try:
        up = data["upstream"]
        targets = {t: Target(t, v["build_repo"], v.get("plugin_key", name)) for t, v in data["targets"].items()}
        return Plugin(name, plugin_dir, up["repo"], up.get("path", "").strip("/"), up.get("ref", "main"), targets)
    except KeyError as exc:
        raise ConfigError(f"{file}: missing {exc}") from None


def names(root: Path) -> list[str]:
    return sorted(p.parent.name for p in (root / "plugins").glob("*/plugin.toml"))
```

- [ ] **Step 4: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_ledger tests.test_config -v`. Expected: 10 tests OK.

- [ ] **Step 5: Commit**

```bash
git add factory/ledger.py factory/config.py tests/test_ledger.py tests/test_config.py
git commit -m "factory: ledger parsing and plugin.toml loading"
```

---

### Task 3: upstream fetch, `new`, templates, test sandbox

**Files:**
- Create:
  - `factory/upstream.py`, `factory/new.py`
  - `factory/templates/plugin.toml`, `factory/templates/port.py`, `factory/templates/CUSTOMIZATIONS.md`, `factory/templates/README.md`
  - `tests/helpers.py`, `tests/test_new.py`

**Interfaces:**
- Consumes: `gitutil.git`, `config.ConfigError`, `config.load`
- Produces:
  - `upstream.fetch(repo: str, path: str, ref: str, dest: Path) -> str` (`dest` must not exist; returns the commit SHA)
  - `upstream.count_ahead(repo: str, path: str, ref: str, since: str, dest: Path) -> int`
  - `new.LEDGER = "CUSTOMIZATIONS.md"`
  - `new.clone_path(root: Path, plugin: str, target: str) -> Path` (`root/builds/<target>/<plugin>`)
  - `new.default_remote(owner: str, name: str, target: str) -> str`
  - `new.new(root: Path, name: str, target: str, upstream_spec: str, remote: str, *, github_repo: str | None = None, public: bool = True) -> Path`
  - `tests.helpers.Sandbox` with `.root`, `.upstream`, `.remote`, `.profiles`, `.clone`, `.write_upstream(rel, text, delete=False)`, `.remote_rev(branch)`, `.cleanup()`, and `COPY_HOOK`

- [ ] **Step 1: Write the templates** (used by `new`; `{{NAME}}`-style placeholders are replaced verbatim).

`factory/templates/plugin.toml`:
```toml
[upstream]
repo = "{{REPO}}"
path = "{{PATH}}"
ref = "main"

[targets.{{TARGET}}]
build_repo = "{{REMOTE}}"
plugin_key = "{{NAME}}"
```

`factory/templates/port.py`:
```python
"""Port hook for {{NAME}} on {{TARGET}}: fill `out` (empty apart from .git) from the upstream tree in `src`.

`ctx` has: plugin, target, here (this folder, for overlay files), upstream_sha, ref, and `version`,
which you may set so build commits read "{{NAME}} <version> @ <sha>".
"""
import json
import shutil


def port(src, out, ctx):
    shutil.copytree(src, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    if not (out / "plugin.json").exists():
        manifest = {"name": "{{NAME}}", "version": f"0.0.0+{ctx.target}.{ctx.upstream_sha[:7]}"}
        (out / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")
```

`factory/templates/CUSTOMIZATIONS.md`:
````markdown
# {{NAME}} customizations

This file lists the personal changes made on top of the {{TARGET}} build of {{NAME}}. It exists only on the `main` branch.

- `upstream` holds the exact build output from agent-plugin-factory. Never edit it by hand.
- `main` is `upstream` plus the changes listed here. Install this branch.
- `git diff refs/heads/upstream main --` shows the full set of changes.
- Upstream comes in by merge (`python3 -m factory sync {{NAME}}`). Never rebase or rewrite `main`: `hermes plugins update` only fast-forwards.

Each change has one entry. Its commits start with its ID, for example `C-001: …`. When resolving a merge conflict, re-apply the **Intent** instead of keeping the old wording. Status is `active` or `retired`. Retire an entry when upstream covers it or you no longer want it, and keep it as history.

Entry format:

```
## C-NNN — <area>: <short title>  [active]
Intent: what must be true afterwards, written so it survives upstream rewording.
Why: the reason for the change.
Touches: path/to/file, path/to/folder/
Check: how to confirm it still holds.
```

<!-- entries below, newest last -->
````

`factory/templates/README.md`:
```markdown
# {{NAME}}-{{TARGET}}

[{{NAME}}]({{REPO}}) built for {{TARGET}}, with personal customizations. Generated by [scotu/agent-plugin-factory](https://github.com/scotu/agent-plugin-factory).

- **`upstream`** is the exact build output. `UPSTREAM` records the upstream commit, and `FACTORY` records the factory commit. Never edit it by hand.
- **`main`** is `upstream` plus the changes in `CUSTOMIZATIONS.md`. Install this branch.

See the upstream project for its license.
```

- [ ] **Step 2: Write the sandbox helper** `tests/helpers.py`:

```python
"""A throwaway world for end-to-end tests: a fake upstream repo, a bare repo standing in for GitHub,
a factory root with plugin `demo` (target `hermes`) created through `new`, and an empty profiles dir."""
import tempfile
from pathlib import Path

from factory.gitutil import git
from factory.new import clone_path, new

COPY_HOOK = '''import shutil


def port(src, out, ctx):
    if (src / "FAIL").exists():
        raise RuntimeError("boom")
    shutil.copytree(src, out, dirs_exist_ok=True)
    ctx.version = "1.0"
'''


class Sandbox:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name).resolve()
        self.upstream = base / "upstream"
        self.remote = base / "remote.git"
        self.root = base / "factory"
        self.profiles = base / "profiles"
        self.profiles.mkdir()
        (self.upstream / "plug").mkdir(parents=True)
        git(self.upstream, "init", "-q", "-b", "main")
        (self.upstream / "other.txt").write_text("not part of the plugin\n")
        self.write_upstream("plugin.json", '{"name": "demo"}\n')
        self.write_upstream("a.txt", "one\ntwo\nthree\n")
        self.remote.mkdir()
        git(self.remote, "init", "-q", "--bare", "-b", "main")
        self.root.mkdir()
        new(self.root, "demo", "hermes", f"{self.upstream.as_uri()}#plug", self.remote.as_uri())
        (self.root / "plugins" / "demo" / "hermes" / "port.py").write_text(COPY_HOOK)
        self.clone = clone_path(self.root, "demo", "hermes")

    def write_upstream(self, rel: str, text: str, delete: bool = False) -> str:
        path = self.upstream / "plug" / rel
        if delete:
            path.unlink()
        else:
            path.write_text(text)
        git(self.upstream, "add", "-A")
        git(self.upstream, "commit", "-q", "-m", f"change {rel}")
        return git(self.upstream, "rev-parse", "HEAD")

    def remote_rev(self, branch: str) -> str:
        return git(self.remote, "rev-parse", f"refs/heads/{branch}")

    def cleanup(self):
        self._tmp.cleanup()
```

- [ ] **Step 3: Write the failing tests** in `tests/test_new.py`:

```python
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

    def test_refuses_existing_plugin(self):
        with self.assertRaisesRegex(config.ConfigError, "already exists"):
            from factory.new import new
            new(self.sb.root, "demo", "hermes", "x#y", self.sb.remote.as_uri())

    def test_fetch_checks_out_only_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "u"
            sha = upstream.fetch(self.sb.upstream.as_uri(), "plug", "main", dest)
            self.assertEqual(sha, git(self.sb.upstream, "rev-parse", "HEAD"))
            self.assertTrue((dest / "plug" / "a.txt").exists())
            self.assertFalse((dest / "other.txt").exists())

    def test_count_ahead(self):
        first = git(self.sb.upstream, "rev-parse", "HEAD")
        self.sb.write_upstream("b.txt", "b\n")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(upstream.count_ahead(self.sb.upstream.as_uri(), "plug", "main", first,
                                                  Path(tmp) / "u"), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the tests and confirm they fail.** Run `python3 -m unittest tests.test_new -v`. Expected: `ModuleNotFoundError: No module named 'factory.new'`.

- [ ] **Step 5: Implement.**

`factory/upstream.py`:
```python
"""Fetch an upstream plugin tree, and count how far upstream has moved."""
from pathlib import Path

from .gitutil import git


def fetch(repo: str, path: str, ref: str, dest: Path) -> str:
    """Clone `repo` into `dest` (which must not exist), check out `ref` with only `path` present,
    and return the checked-out commit SHA."""
    sparse = ["--sparse"] if path else []
    git(dest.parent, "clone", "-q", "--filter=blob:none", *sparse, "--no-checkout", repo, str(dest))
    if path:
        git(dest, "sparse-checkout", "set", path)
    git(dest, "checkout", "-q", ref)
    return git(dest, "rev-parse", "HEAD")


def count_ahead(repo: str, path: str, ref: str, since: str, dest: Path) -> int:
    """Commits on `ref` after `since` that touch `path`."""
    git(dest.parent, "clone", "-q", "--bare", "--filter=blob:none", repo, str(dest))
    return int(git(dest, "rev-list", "--count", f"{since}..{ref}", "--", path or "."))
```

`factory/new.py`:
```python
"""Create a plugin folder from templates and its build repo (upstream: empty init commit; main: ledger + README)."""
import subprocess
from pathlib import Path

from .config import ConfigError
from .gitutil import git

LEDGER = "CUSTOMIZATIONS.md"
TEMPLATES = Path(__file__).parent / "templates"


def clone_path(root: Path, plugin: str, target: str) -> Path:
    return root / "builds" / target / plugin


def default_remote(owner: str, name: str, target: str) -> str:
    return f"git@github.com:{owner}/{name}-{target}.git"


def _fill(template: str, **values: str) -> str:
    text = (TEMPLATES / template).read_text()
    for key, value in values.items():
        text = text.replace("{{" + key.upper() + "}}", value)
    return text


def _gh(*args: str) -> None:
    subprocess.run(["gh", *args], check=True, capture_output=True, text=True)


def new(root: Path, name: str, target: str, upstream_spec: str, remote: str, *,
        github_repo: str | None = None, public: bool = True) -> Path:
    plugin_dir = root / "plugins" / name
    clone = clone_path(root, name, target)
    for path in (plugin_dir, clone):
        if path.exists():
            raise ConfigError(f"{path} already exists")
    repo, _, sub = upstream_spec.partition("#")
    values = dict(name=name, target=target, repo=repo, path=sub.strip("/"), remote=remote)

    (plugin_dir / target).mkdir(parents=True)
    (plugin_dir / "plugin.toml").write_text(_fill("plugin.toml", **values))
    (plugin_dir / target / "port.py").write_text(_fill("port.py", **values))

    if github_repo:
        _gh("repo", "create", github_repo, "--public" if public else "--private",
            "--description", f"{name} built for {target} by agent-plugin-factory")
    clone.mkdir(parents=True)
    git(clone, "init", "-q", "-b", "upstream")
    git(clone, "commit", "-q", "--allow-empty", "-m", "init")
    git(clone, "switch", "-q", "-c", "main")
    (clone / LEDGER).write_text(_fill(LEDGER, **values))
    (clone / "README.md").write_text(_fill("README.md", **values))
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "C-000: add customization ledger")
    git(clone, "remote", "add", "origin", remote)
    git(clone, "push", "-q", "-u", "origin", "main", "upstream")
    if github_repo:
        _gh("repo", "edit", github_repo, "--default-branch", "main")
    return plugin_dir
```

- [ ] **Step 6: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_new -v`. Expected: 5 tests OK. Lines like `warning: filtering not recognized by server` from local clones are fine.

- [ ] **Step 7: Commit**

```bash
git add factory/upstream.py factory/new.py factory/templates tests/helpers.py tests/test_new.py
git commit -m "factory: upstream fetch, new plugin + build repo, test sandbox"
```

---

### Task 4: sync (build, stamp, merge, push)

**Files:**
- Create: `factory/build.py`, `tests/test_sync.py`

**Interfaces:**
- Consumes: `config.load`, `config.ConfigError`, `ledger.parse`, `ledger.touched`, `upstream.fetch`, `new.clone_path`, `new.LEDGER`, and everything in `gitutil`
- Produces:
  - `build.MANIFESTS = {"hermes": "plugin.json"}`
  - `build.SyncError(RuntimeError)`, `build.HookError(SyncError)`
  - `build.Context(plugin, target, here: Path, upstream_sha, ref, version: str | None = None)`
  - `build.SyncResult(clone: Path, upstream_sha: str, built: str, main: str, reviews: list[Entry], conflicts: list[str], pushed: bool, push_error: str)`
  - `build.sync(root: Path, name: str, target: str, ref: str | None = None) -> SyncResult`

- [ ] **Step 1: Write the failing tests** in `tests/test_sync.py`:

```python
import tempfile
import unittest
from pathlib import Path

from factory import build, config
from factory.gitutil import git, is_dirty
from tests.helpers import Sandbox


def customize(clone: Path, rel: str, text: str, msg: str, ledger_entry: str = "") -> None:
    (clone / rel).write_text(text)
    if ledger_entry:
        with (clone / "CUSTOMIZATIONS.md").open("a") as f:
            f.write("\n" + ledger_entry)
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", msg)


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.first = build.sync(self.sb.root, "demo", "hermes")

    def tearDown(self):
        self.sb.cleanup()

    def test_first_sync_builds_merges_and_pushes(self):
        r = self.first
        self.assertEqual((r.conflicts, r.pushed), ([], True))
        self.assertEqual(r.upstream_sha, git(self.sb.upstream, "rev-parse", "HEAD"))
        self.assertEqual(self.sb.remote_rev("upstream"), r.built)
        self.assertEqual(self.sb.remote_rev("main"), r.main)
        self.assertEqual(git(self.sb.remote, "show", "refs/heads/main:a.txt"), "one\ntwo\nthree")
        stamp = git(self.sb.remote, "show", "refs/heads/upstream:UPSTREAM")
        self.assertEqual(stamp, f"repo: {self.sb.upstream.as_uri()}\npath: plug\nref: main\ncommit: {r.upstream_sha}")
        self.assertEqual(git(self.sb.remote, "show", "refs/heads/upstream:FACTORY"), "commit: unknown")
        self.assertEqual(git(self.sb.remote, "log", "-1", "--format=%s", "refs/heads/upstream"),
                         f"demo 1.0 @ {r.upstream_sha[:12]}")
        self.assertIn("C-000", git(self.sb.clone, "log", "--format=%s", "main"))
        self.assertEqual(git(self.sb.clone, "branch", "--show-current"), "main")

    def test_rerun_without_changes_is_noop(self):
        again = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual((again.built, again.main, again.conflicts, again.pushed),
                         (self.first.built, self.first.main, [], True))

    def test_customization_survives_upstream_change(self):
        customize(self.sb.clone, "a.txt", "ONE\ntwo\nthree\n", "C-001: shout")
        self.sb.write_upstream("b.txt", "bee\n")
        r = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual((r.conflicts, r.pushed), ([], True))
        self.assertEqual((self.sb.clone / "a.txt").read_text(), "ONE\ntwo\nthree\n")
        self.assertEqual((self.sb.clone / "b.txt").read_text(), "bee\n")
        self.assertEqual(self.sb.remote_rev("main"), r.main)

    def test_review_notice_for_touched_entries(self):
        entry = "## C-001 — a: shout  [active]\nIntent: x\nTouches: a.txt\n"
        customize(self.sb.clone, "a.txt", "ONE\ntwo\nthree\n", "C-001: shout", entry)
        self.sb.write_upstream("a.txt", "one\ntwo\nTHREE\n")
        r = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual([e.id for e in r.reviews], ["C-001"])
        self.assertEqual((self.sb.clone / "a.txt").read_text(), "ONE\ntwo\nTHREE\n")

    def test_conflict_then_resolution_pushes(self):
        customize(self.sb.clone, "a.txt", "one\nmine\nthree\n", "C-001: mine")
        self.sb.write_upstream("a.txt", "one\ntheirs\nthree\n")
        remote_main = self.sb.remote_rev("main")
        r = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual((r.conflicts, r.pushed), (["a.txt"], False))
        self.assertEqual(self.sb.remote_rev("main"), remote_main)
        self.assertEqual(self.sb.remote_rev("upstream"), self.first.built)

        (self.sb.clone / "a.txt").write_text("one\nmine and theirs\nthree\n")
        git(self.sb.clone, "add", "a.txt")
        git(self.sb.clone, "commit", "-q", "--no-edit")
        again = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual((again.conflicts, again.pushed), ([], True))
        self.assertEqual(git(self.sb.remote, "show", "refs/heads/main:a.txt"), "one\nmine and theirs\nthree")
        self.assertEqual(self.sb.remote_rev("upstream"), again.built)

    def test_unfinished_merge_refused(self):
        customize(self.sb.clone, "a.txt", "one\nmine\nthree\n", "C-001: mine")
        self.sb.write_upstream("a.txt", "one\ntheirs\nthree\n")
        build.sync(self.sb.root, "demo", "hermes")
        git(self.sb.clone, "checkout", "--ours", "--", "a.txt")
        git(self.sb.clone, "add", "a.txt")
        with self.assertRaisesRegex(build.SyncError, "unfinished merge"):
            build.sync(self.sb.root, "demo", "hermes")

    def test_failing_hook_leaves_state_clean(self):
        self.sb.write_upstream("FAIL", "x\n")
        with self.assertRaisesRegex(build.HookError, "boom"):
            build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual(git(self.sb.clone, "rev-parse", "refs/heads/upstream"), self.first.built)
        self.assertEqual(git(self.sb.clone, "branch", "--show-current"), "main")
        self.assertFalse(is_dirty(self.sb.clone))

    def test_missing_manifest_fails(self):
        self.sb.write_upstream("plugin.json", "", delete=True)
        with self.assertRaisesRegex(build.HookError, "no plugin.json"):
            build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual(git(self.sb.clone, "rev-parse", "refs/heads/upstream"), self.first.built)

    def test_dirty_clone_refused(self):
        (self.sb.clone / "scratch.txt").write_text("x\n")
        self.sb.write_upstream("b.txt", "bee\n")
        with self.assertRaisesRegex(build.SyncError, "uncommitted changes"):
            build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual(git(self.sb.clone, "rev-parse", "refs/heads/upstream"), self.first.built)

    def test_missing_clone_is_cloned(self):
        import shutil
        shutil.rmtree(self.sb.clone)
        self.sb.write_upstream("b.txt", "bee\n")
        r = build.sync(self.sb.root, "demo", "hermes")
        self.assertTrue(r.pushed)
        self.assertEqual(git(self.sb.clone, "config", "rerere.enabled"), "true")

    def test_shallow_install_fast_forwards(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "inst"
            git(Path(tmp), "clone", "-q", "--depth", "1", self.sb.remote.as_uri(), str(inst))
            customize(self.sb.clone, "a.txt", "ONE\ntwo\nthree\n", "C-001: shout")
            self.sb.write_upstream("b.txt", "bee\n")
            build.sync(self.sb.root, "demo", "hermes")
            git(inst, "pull", "-q", "--ff-only")
            self.assertEqual((inst / "a.txt").read_text(), "ONE\ntwo\nthree\n")
            self.assertTrue((inst / "b.txt").exists())

    def test_unknown_target(self):
        with self.assertRaisesRegex(config.ConfigError, "no target 'codex'"):
            build.sync(self.sb.root, "demo", "codex")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python3 -m unittest tests.test_sync -v`. Expected: `ModuleNotFoundError: No module named 'factory.build'`.

- [ ] **Step 3: Implement** `factory/build.py`:

```python
"""Build one plugin for one target into its build repo's `upstream` branch, then merge into `main` and push."""
import importlib.util
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import config, ledger, upstream
from .gitutil import git, has_branch, is_dirty, ok, run
from .new import LEDGER, clone_path

MANIFESTS = {"hermes": "plugin.json"}


class SyncError(RuntimeError):
    pass


class HookError(SyncError):
    pass


@dataclass
class Context:
    plugin: str
    target: str
    here: Path
    upstream_sha: str
    ref: str
    version: str | None = None


@dataclass
class SyncResult:
    clone: Path
    upstream_sha: str
    built: str
    main: str = ""
    reviews: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    pushed: bool = False
    push_error: str = ""


def load_hook(here: Path):
    path = here / "port.py"
    if not path.exists():
        raise config.ConfigError(f"missing port hook: {path}")
    spec = importlib.util.spec_from_file_location(f"port_{here.parent.name}_{here.name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.port


def factory_stamp(root: Path) -> str:
    if not ok(root, "rev-parse", "--verify", "--quiet", "HEAD"):
        return "commit: unknown\n"
    stamp = f"commit: {git(root, 'rev-parse', 'HEAD')}\n"
    return stamp + ("dirty: true\n" if is_dirty(root) else "")


def prepare(clone: Path, remote: str) -> None:
    """Clone or fast-forward the build repo and leave it on `upstream`. Never forces anything."""
    if not (clone / ".git").exists():
        clone.parent.mkdir(parents=True, exist_ok=True)
        git(clone.parent, "clone", "-q", remote, str(clone))
    git(clone, "config", "rerere.enabled", "true")
    if is_dirty(clone):
        raise SyncError(f"{clone} has uncommitted changes or an unfinished merge; commit or resolve them first")
    git(clone, "fetch", "-q", "origin")
    if not ok(clone, "rev-parse", "--verify", "--quiet", "refs/remotes/origin/upstream"):
        raise SyncError(f"{remote} has no 'upstream' branch; build repos are created with `python3 -m factory new`")
    for branch in ("main", "upstream"):
        if not has_branch(clone, branch):
            git(clone, "branch", branch, f"refs/remotes/origin/{branch}")
        git(clone, "switch", "-q", branch)
        if not ok(clone, "merge", "-q", "--ff-only", f"refs/remotes/origin/{branch}"):
            raise SyncError(f"{branch} in {clone} has diverged from origin; reconcile it by hand (never force-push main)")


def _empty(clone: Path) -> None:
    for child in clone.iterdir():
        if child.name != ".git":
            shutil.rmtree(child) if child.is_dir() else child.unlink()


def sync(root: Path, name: str, target: str, ref: str | None = None) -> SyncResult:
    plugin = config.load(root, name)
    if target not in plugin.targets:
        raise config.ConfigError(f"plugin '{name}' has no target '{target}' (has: {', '.join(plugin.targets)})")
    here = plugin.dir / target
    port = load_hook(here)
    ref = ref or plugin.ref
    clone = clone_path(root, name, target)

    with tempfile.TemporaryDirectory() as tmp:
        src_repo = Path(tmp) / "upstream"
        sha = upstream.fetch(plugin.repo, plugin.path, ref, src_repo)
        src = src_repo / plugin.path if plugin.path else src_repo
        prepare(clone, plugin.targets[target].build_repo)
        before = git(clone, "rev-parse", "HEAD")
        ctx = Context(name, target, here, sha, ref)
        manifest = MANIFESTS.get(target, "plugin.json")
        try:
            _empty(clone)
            port(src, clone, ctx)
            if not (clone / manifest).exists():
                raise HookError(f"hook produced no {manifest}")
        except Exception as exc:
            git(clone, "reset", "-q", "--hard", before)
            git(clone, "clean", "-qfdx")
            git(clone, "switch", "-q", "main")
            raise HookError(f"port hook for {name}/{target} failed: {exc}") from exc

    (clone / "UPSTREAM").write_text(f"repo: {plugin.repo}\npath: {plugin.path}\nref: {ref}\ncommit: {sha}\n")
    (clone / "FACTORY").write_text(factory_stamp(root))
    label = f"{name} {ctx.version}" if ctx.version else name
    git(clone, "add", "-A")
    if is_dirty(clone):
        git(clone, "commit", "-q", "-m", f"{label} @ {sha[:12]}")
    built = git(clone, "rev-parse", "HEAD")

    git(clone, "switch", "-q", "main")
    changed = git(clone, "diff", "--name-only", before, built).split() if before != built else []
    text = (clone / LEDGER).read_text() if (clone / LEDGER).exists() else ""
    result = SyncResult(clone, sha, built, reviews=ledger.touched(ledger.parse(text), changed))
    merge = run(clone, "merge", "--no-ff", "-q", "refs/heads/upstream", "-m", f"merge upstream {label} @ {sha[:12]}")
    result.main = git(clone, "rev-parse", "HEAD")
    if merge.returncode:
        result.conflicts = git(clone, "diff", "--name-only", "--diff-filter=U").split()
        if not result.conflicts:
            raise SyncError(f"merge into main failed in {clone}:\n{(merge.stderr or merge.stdout).strip()}")
        return result
    push = run(clone, "push", "-q", "origin", "main", "upstream")
    result.pushed = push.returncode == 0
    result.push_error = "" if result.pushed else (push.stderr or push.stdout).strip()
    return result
```

- [ ] **Step 4: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_sync -v`. Expected: 12 tests OK.

- [ ] **Step 5: Run the whole suite.** Run `python3 -m unittest discover -s tests -v`. Expected: all OK.

- [ ] **Step 6: Commit**

```bash
git add factory/build.py tests/test_sync.py
git commit -m "factory: sync builds upstream branch, merges into main, pushes"
```

---

### Task 5: install and status

**Files:**
- Create: `factory/install.py`, `factory/status.py`, `tests/test_install_status.py`

**Interfaces:**
- Consumes: `build.sync`, `new.clone_path`, `new.LEDGER`, `config.load`, `ledger.parse`, `upstream.count_ahead`, and `gitutil`
- Produces:
  - `install.DEFAULT_PROFILES: Path` (`~/.hermes/profiles`)
  - `install.installed(profiles_dir: Path, plugin_key: str, clone: Path) -> list[tuple[str, str]]` (profile and revision; only installs whose source is `clone.resolve().as_uri()`)
  - `install.update(profiles_dir: Path, plugin_key: str, clone: Path) -> list[str]` (the profiles that were updated)
  - `status.lines(root: Path, names: list[str], profiles_dir: Path) -> list[str]`

- [ ] **Step 1: Write the failing tests** in `tests/test_install_status.py`:

```python
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

    def test_status_not_cloned(self):
        import shutil
        shutil.rmtree(self.sb.clone)
        self.assertEqual(status.lines(self.sb.root, ["demo"], self.sb.profiles), ["demo/hermes: not cloned (run sync)"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python3 -m unittest tests.test_install_status -v`. Expected: `ImportError` (no `install` or `status` modules).

- [ ] **Step 3: Implement.**

`factory/install.py`:
```python
"""Hermes profiles that installed a plugin from a local build clone (file://), and updating them."""
import json
import subprocess
from pathlib import Path

DEFAULT_PROFILES = Path.home() / ".hermes" / "profiles"


def installed(profiles_dir: Path, plugin_key: str, clone: Path) -> list[tuple[str, str]]:
    source = clone.resolve().as_uri()
    found = []
    for meta in sorted(profiles_dir.glob("*/plugins/.install-metadata.json")):
        entry = json.loads(meta.read_text()).get(plugin_key)
        if isinstance(entry, dict) and entry.get("source") == source:
            found.append((meta.parents[1].name, str(entry.get("revision", ""))))
    return found


def update(profiles_dir: Path, plugin_key: str, clone: Path) -> list[str]:
    profiles = [profile for profile, _ in installed(profiles_dir, plugin_key, clone)]
    for profile in profiles:
        subprocess.run(["hermes", "-p", profile, "plugins", "update", plugin_key],
                       check=True, capture_output=True, text=True)
    return profiles
```

`factory/status.py`:
```python
"""One line per plugin target: build state, upstream drift, customizations, installs."""
import tempfile
from pathlib import Path

from . import config, install, ledger, upstream
from .gitutil import GitError, git, ok
from .new import LEDGER, clone_path


def _short(clone: Path, branch: str) -> str:
    return git(clone, "rev-parse", "--short", f"refs/heads/{branch}")


def lines(root: Path, names: list[str], profiles_dir: Path) -> list[str]:
    out = []
    for name in names:
        plugin = config.load(root, name)
        for target, spec in plugin.targets.items():
            clone = clone_path(root, name, target)
            head = f"{name}/{target}"
            if not (clone / ".git").exists():
                out.append(f"{head}: not cloned (run sync)")
                continue
            stamp = git(clone, "show", "refs/heads/upstream:UPSTREAM") \
                if ok(clone, "cat-file", "-e", "refs/heads/upstream:UPSTREAM") else ""
            built_from = dict(l.split(": ", 1) for l in stamp.splitlines() if ": " in l).get("commit", "")
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    ahead = str(upstream.count_ahead(plugin.repo, plugin.path, plugin.ref, built_from, Path(tmp) / "u"))
            except GitError:
                ahead = "?"
            text = git(clone, "show", f"refs/heads/main:{LEDGER}") \
                if ok(clone, "cat-file", "-e", f"refs/heads/main:{LEDGER}") else ""
            active = sum(1 for e in ledger.parse(text) if e.status == "active")
            installs = ", ".join(f"{p}@{r[:7]}" for p, r in install.installed(profiles_dir, spec.plugin_key, clone))
            out.append(f"{head}: upstream {_short(clone, 'upstream')} (from {built_from[:12] or 'nothing yet'}, "
                       f"{ahead} new upstream commits on {plugin.ref}), main {_short(clone, 'main')}, "
                       f"{active} active customizations, installed: {installs or 'none'}")
    return out
```

- [ ] **Step 4: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_install_status -v`. Expected: 3 tests OK.

- [ ] **Step 5: Commit**

```bash
git add factory/install.py factory/status.py tests/test_install_status.py
git commit -m "factory: hermes install lookup/update and status"
```

---

### Task 6: CLI

**Files:**
- Create: `factory/__main__.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `build.sync`, `build.SyncError`, `config.load`, `config.names`, `config.ConfigError`, `install.update`, `install.DEFAULT_PROFILES`, `new.new`, `new.default_remote`, `status.lines`, `gitutil.GitError`
- Produces: `python3 -m factory [--root DIR] [--profiles DIR] {sync PLUGIN [--target T] [--ref R] [--install] | new PLUGIN --upstream URL[#SUBDIR] [--target hermes] [--owner scotu] [--private] [--remote URL] | status [PLUGIN]}`. It exits 0 on success and 1 on any conflict, push failure, or error.

- [ ] **Step 1: Write the failing tests** in `tests/test_cli.py`:

```python
import subprocess
import sys
import unittest
from pathlib import Path

from factory.gitutil import git
from tests.helpers import Sandbox

REPO = Path(__file__).resolve().parent.parent


class CliTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "factory", "--root", str(self.sb.root),
                               "--profiles", str(self.sb.profiles), *args],
                              cwd=REPO, capture_output=True, text=True)

    def test_sync_and_status(self):
        r = self.cli("sync", "demo")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("demo/hermes: upstream", r.stdout)
        self.assertIn("pushed", r.stdout)
        r = self.cli("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("installed: none", r.stdout)

    def test_conflict_exits_1(self):
        self.cli("sync", "demo")
        (self.sb.clone / "a.txt").write_text("one\nmine\nthree\n")
        git(self.sb.clone, "commit", "-qam", "C-001: mine")
        self.sb.write_upstream("a.txt", "one\ntheirs\nthree\n")
        r = self.cli("sync", "demo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MERGE CONFLICT", r.stdout)
        self.assertIn("a.txt", r.stdout)

    def test_cli_unknown_plugin_exits_1(self):
        r = self.cli("sync", "nope")
        self.assertEqual(r.returncode, 1)
        self.assertIn("error: unknown plugin 'nope'", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_new_with_explicit_remote(self):
        remote = self.sb.root.parent / "two.git"
        remote.mkdir()
        git(remote, "init", "-q", "--bare", "-b", "main")
        r = self.cli("new", "two", "--upstream", f"{self.sb.upstream.as_uri()}#plug", "--remote", remote.as_uri())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.sb.root / "plugins" / "two" / "hermes" / "port.py").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python3 -m unittest tests.test_cli -v`. Expected: failures with `No module named factory.__main__`.

- [ ] **Step 3: Implement** `factory/__main__.py`:

```python
"""python3 -m factory: build customized agent plugins from their upstreams."""
import argparse
import subprocess
import sys
from pathlib import Path

from . import build, config, install, status
from .gitutil import GitError
from .new import default_remote, new

ROOT = Path(__file__).resolve().parent.parent


def cmd_sync(args) -> int:
    plugin = config.load(args.root, args.plugin)
    code = 0
    for target in [args.target] if args.target else list(plugin.targets):
        r = build.sync(args.root, args.plugin, target, args.ref)
        print(f"{args.plugin}/{target}: upstream {r.built[:7]} built from {r.upstream_sha[:12]}")
        for entry in r.reviews:
            print(f"  review {entry.title} (upstream changed its files)")
        if r.conflicts:
            print(f"  MERGE CONFLICT on main in {r.clone}:")
            for path in r.conflicts:
                print(f"    {path}")
            print(f"  Re-apply each affected entry's Intent from {build.LEDGER}, commit, then run sync again.")
            code = 1
            continue
        print(f"  main {r.main[:7]}, " + ("pushed" if r.pushed else f"NOT pushed: {r.push_error}"))
        if not r.pushed:
            code = 1
        if args.install and target == "hermes":
            for profile in install.update(args.profiles, plugin.targets[target].plugin_key, r.clone):
                print(f"  updated profile {profile}")
    return code


def cmd_new(args) -> int:
    github_repo = None if args.remote else f"{args.owner}/{args.plugin}-{args.target}"
    remote = args.remote or default_remote(args.owner, args.plugin, args.target)
    plugin_dir = new(args.root, args.plugin, args.target, args.upstream, remote,
                     github_repo=github_repo, public=not args.private)
    print(f"created {plugin_dir} and build repo {remote}")
    print(f"next: write {plugin_dir / args.target / 'port.py'}, then `python3 -m factory sync {args.plugin}`")
    return 0


def cmd_status(args) -> int:
    for line in status.lines(args.root, [args.plugin] if args.plugin else config.names(args.root), args.profiles):
        print(line)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m factory", description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    p.add_argument("--profiles", type=Path, default=install.DEFAULT_PROFILES, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sync", help="build from upstream, merge into main, push")
    s.add_argument("plugin")
    s.add_argument("--target")
    s.add_argument("--ref", help="upstream git ref (default: plugin.toml ref)")
    s.add_argument("--install", action="store_true", help="update Hermes profiles installed from the build clone")
    s.set_defaults(func=cmd_sync)

    n = sub.add_parser("new", help="create a plugin folder and its build repo")
    n.add_argument("plugin")
    n.add_argument("--upstream", required=True, help="git URL, optionally #subdir")
    n.add_argument("--target", default="hermes")
    n.add_argument("--owner", default="scotu")
    n.add_argument("--private", action="store_true")
    n.add_argument("--remote", help="existing empty build repo URL (skips creating it on GitHub)")
    n.set_defaults(func=cmd_new)

    st = sub.add_parser("status", help="show build state for every plugin")
    st.add_argument("plugin", nargs="?")
    st.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    args.root = args.root.resolve()
    try:
        return args.func(args)
    except (config.ConfigError, build.SyncError, GitError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or ""
        print(f"error: {exc}{(chr(10) + detail.strip()) if detail else ''}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_cli -v`. Expected: 4 tests OK. Then run `python3 -m unittest discover -s tests -v`. Expected: all OK.

- [ ] **Step 5: Commit**

```bash
git add factory/__main__.py tests/test_cli.py
git commit -m "factory: CLI for sync, new, status"
```

---

### Task 7: pstack as the first plugin; remove sync.py

**Files:**
- Create: `plugins/pstack/plugin.toml`, `plugins/pstack/hermes/port.py`
- Move: `overlay/skills/*` → `plugins/pstack/hermes/overlay/skills/*`
- Delete: `sync.py`
- Modify: `README.md` (full rewrite), `LICENSE` (overlay path), `.gitignore`

**Interfaces:**
- Consumes: `build.Context` fields `upstream_sha`, `here`, and `version`
- Produces: `plugins/pstack/hermes/port.py::port(src, out, ctx)`, which reproduces exactly what `sync.py` produced, except for `UPSTREAM`, which `factory` now writes.

- [ ] **Step 1: Move the overlay and add the config.**

```bash
mkdir -p plugins/pstack/hermes
git mv overlay plugins/pstack/hermes/overlay
```

`plugins/pstack/plugin.toml`:
```toml
[upstream]
repo = "https://github.com/cursor/plugins"
path = "pstack"
ref = "main"

[targets.hermes]
build_repo = "git@github.com:scotu/pstack-hermes-build.git"
plugin_key = "pstack"
```

- [ ] **Step 2: Write the hook** `plugins/pstack/hermes/port.py`. This is `sync.py`'s pstack-specific logic, unchanged apart from the plumbing:

```python
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
```

- [ ] **Step 3: Delete `sync.py`, then update `.gitignore` and `LICENSE`.**

```bash
git rm -q sync.py
printf 'build/\nbuilds/\n__pycache__/\n.DS_Store\n' > .gitignore
```
In `LICENSE`, replace `Parts of overlay/ adapt text from pstack` with `Parts of plugins/pstack/hermes/overlay/ adapt text from pstack`.

- [ ] **Step 4: Check that the pstack build is unchanged.** Run it against a local mirror so nothing is pushed to GitHub:

```bash
S=$(mktemp -d)
git clone -q --mirror git@github.com:scotu/pstack-hermes-build.git "$S/remote.git"
rsync -a --exclude build --exclude builds ./ "$S/factory/"
sed -i '' "s|build_repo = .*|build_repo = \"file://$S/remote.git\"|" "$S/factory/plugins/pstack/plugin.toml"
(cd "$S/factory" && python3 -m factory sync pstack --ref ecc249f1e306fc64ddf83c7bed16cacf7c2239db)
git -C "$S/factory/builds/hermes/pstack" diff --stat 0a84f1d refs/heads/upstream
```
Expected: the sync prints `pushed` (to the local mirror only). The diff lists only `FACTORY | 2 +` (one new file with the factory commit and `dirty: true`). Any other file in the diff means the hook drifted from `sync.py`; fix it before continuing. Then `rm -rf "$S"`.

- [ ] **Step 5: Rewrite `README.md`:**

````markdown
# agent-plugin-factory

Builds upstream agent plugins for the agents we use, with personal customizations that survive upstream updates. For now the only target is [Hermes](https://hermes-agent.nousresearch.com/).

| Plugin | Upstream | Build repo |
|---|---|---|
| pstack | [cursor/plugins/pstack](https://github.com/cursor/plugins/tree/main/pstack) | [scotu/pstack-hermes](https://github.com/scotu/pstack-hermes) |

## How it works

Each plugin and target has its own **build repo**, `scotu/<plugin>-<target>`. It is a standalone plugin that you can install directly. It has two branches:

- **`upstream`** is the exact build output: the upstream tree run through the plugin's port hook. `UPSTREAM` records the upstream commit, and `FACTORY` records the factory commit that built it. Never edit it by hand.
- **`main`** is `upstream` plus personal changes. Hermes installs this branch.

Each personal change is a `C-NNN: …` commit on `main`, with an entry in that repo's `CUSTOMIZATIONS.md`: the intent, the reason, the files it touches, and how to check it. `git diff refs/heads/upstream main --` shows the whole fork.

`python3 -m factory sync <plugin>` does the following:
1. Fetches upstream and clones or fast-forwards the build repo into `builds/<target>/<plugin>/` (gitignored).
2. Runs the port hook into `upstream` and commits.
3. Lists the ledger entries whose files upstream changed, so you can check whether upstream now covers them.
4. Merges into `main`, with git rerere on, and pushes both branches.

On a conflict it stops without pushing. Re-apply each affected entry's intent, commit in the build clone, and run `sync` again.

Never rebase or reset `main` in a build repo. `hermes plugins update` pulls with `--ff-only`.

## Commands

```
python3 -m factory sync <plugin> [--ref <git-ref>] [--install]   # --install: update Hermes profiles using the build clone
python3 -m factory status [<plugin>]
python3 -m factory new <plugin> --upstream <git-url>[#subdir]     # creates plugins/<plugin>/ and scotu/<plugin>-hermes
python3 -m unittest discover -s tests -v
```

First install into a Hermes profile:
```
hermes -p <profile> plugins install file://$PWD/builds/hermes/<plugin> --enable
```

## Adding a plugin

1. Run `python3 -m factory new <name> --upstream <git-url>#<subdir>`. It writes `plugins/<name>/plugin.toml` and a stub `plugins/<name>/hermes/port.py`, which copies the tree as is. It also creates the public build repo.
2. Write the port hook, `port(src, out, ctx)`:
   - `src` is the upstream subtree and `out` is the empty build folder.
   - `ctx.here` is the hook's own folder, so overlay files can live next to it.
   - `ctx.upstream_sha` is the upstream commit. You can set `ctx.version`, which appears in commit messages.
   - The output must contain `plugin.json`.
3. Run `python3 -m factory sync <name>`, then install it.

## pstack on Hermes

`plugins/pstack/hermes/port.py` makes these changes to the upstream text:

1. **Manifest.** A root `plugin.json` (Agent Plugins v1) replaces `.cursor-plugin/plugin.json`. Its version is `<upstream>+hermes.<sha>`.
2. **Names.** Each `SKILL.md` `name:` is set to its directory name, which Hermes requires. This fixes `poteto-mode`.
3. **Pointer.** A one-line pointer to the `pstack-on-hermes` skill is added after every skill's frontmatter.
4. **Overlay** (`plugins/pstack/hermes/overlay/skills/`):
   - `pstack-on-hermes` maps Cursor to Hermes: `Task`/`subagent_type` become `delegate_task`, model roles become `pstack-models.md`, `AskQuestion` becomes `clarify`, cloud agents become worktrees, and transcripts become sessions. Upstream `agents/*.md` ship as its `references/`.
   - `setup-pstack` is replaced by a Hermes version that sets `delegation.model` and writes `pstack-models.md`.
5. **Dropped:** `make-bot-ui` (dr-eggbot ships its own), `automations/`, the docs, and the assets.

Skills resolve only under their namespaced name, `agent-plugin-pstack-7171b73f:<name>`.

Known limits:
- There is no per-subagent model on Hermes.
- Named Cursor agents become delegated tasks.
- Cursor cloud agents and `cursor-team-kit` have no Hermes equivalent.
- `disable-model-invocation` is ignored.
- `poteto-mode/scripts` need `bun`, `node` and `gh`.

## License

MIT. pstack is MIT, Copyright (c) 2026 Lauren Tan. See `LICENSE`.
````

- [ ] **Step 6: Run the whole suite.** Run `python3 -m unittest discover -s tests -v`. Expected: all OK.

- [ ] **Step 7: Commit** (not pushed yet; the GitHub rename comes first):

```bash
git add -A
git commit -m "pstack becomes the first factory plugin; remove sync.py"
```

---

### Task 8: rename the GitHub repos

These actions are outward-facing. The spec covers them; run them in this order.

- [ ] **Step 1: Rename the tooling repo, then the build repo.**

```bash
gh repo rename agent-plugin-factory -R scotu/pstack-hermes --yes
gh repo rename pstack-hermes -R scotu/pstack-hermes-build --yes
gh repo edit scotu/agent-plugin-factory --description "Builds upstream agent plugins (pstack, ...) for Hermes, keeping personal customizations mergeable"
gh repo edit scotu/pstack-hermes --description "pstack built for Hermes, with personal customizations (generated by scotu/agent-plugin-factory)"
```
Check: `gh repo view scotu/agent-plugin-factory --json name` and `gh repo view scotu/pstack-hermes --json name,defaultBranchRef` show the new names and `main`.

- [ ] **Step 2: Point the remotes and the config at the new names.**

```bash
git remote set-url origin git@github.com:scotu/agent-plugin-factory.git
git -C build/pstack remote set-url origin git@github.com:scotu/pstack-hermes.git
sed -i '' 's|scotu/pstack-hermes-build.git|scotu/pstack-hermes.git|' plugins/pstack/plugin.toml
git -C build/pstack fetch -q origin && git -C build/pstack status -sb | head -1
```
Expected: `## main...origin/main` with no ahead or behind count.

- [ ] **Step 3: Update the build repo's README and push it as a `C-000` commit.** Replace `build/pstack/README.md` with:

```markdown
# pstack-hermes

[pstack](https://github.com/cursor/plugins/tree/main/pstack) built for [Hermes](https://hermes-agent.nousresearch.com/), with personal customizations. Generated by [scotu/agent-plugin-factory](https://github.com/scotu/agent-plugin-factory). Don't edit the `upstream` branch by hand.

- **`upstream`** is the exact build output. `UPSTREAM` records the upstream commit, and `FACTORY` records the factory commit.
- **`main`** is `upstream` plus the changes in `CUSTOMIZATIONS.md`. Install this branch.

```
hermes -p <profile> plugins install https://github.com/scotu/pstack-hermes --enable
```

pstack is MIT, Copyright (c) 2026 Lauren Tan (see `LICENSE`). The upstream README is in `UPSTREAM-README.md`.
```

In `build/pstack/CUSTOMIZATIONS.md`, replace the line ``- Upstream is brought in by `sync.py` with a merge.`` with ``- Upstream is brought in by `python3 -m factory sync pstack` (scotu/agent-plugin-factory) with a merge.``

```bash
git -C build/pstack add -A
git -C build/pstack commit -qm "C-000: point README and ledger at agent-plugin-factory"
git -C build/pstack push -q origin main
```

- [ ] **Step 4: Commit the config change.**

```bash
git add plugins/pstack/plugin.toml
git commit -m "pstack: build repo is scotu/pstack-hermes"
```

---

### Task 9: move the local folders and reinstall into the Hermes profiles

- [ ] **Step 1: Move the build clone, then rename the tooling folder.**

```bash
cd /Users/matteo/Development/agents
mkdir -p pstack-hermes/builds/hermes
mv pstack-hermes/build/pstack pstack-hermes/builds/hermes/pstack
rmdir pstack-hermes/build
mv pstack-hermes agent-plugin-factory
```

- [ ] **Step 2: Check the factory sees the clone without syncing.** Run `cd /Users/matteo/Development/agents/agent-plugin-factory && python3 -m factory status`. Expected: `pstack/hermes: upstream 0a84f1d (from ecc249f1e306, N new upstream commits on main), main <sha>, 0 active customizations, installed: none`. N is at least 1, since 0.15.6 exists. `none` is correct, because the profiles still point at the old path.

- [ ] **Step 3: Reinstall pstack in each profile from the new path.**

```bash
SRC=file:///Users/matteo/Development/agents/agent-plugin-factory/builds/hermes/pstack
for p in dr-eggbot homelab-ops; do hermes -p "$p" plugins install "$SRC" --force --enable; done
```

- [ ] **Step 4: Verify the installs.**

```bash
python3 -m factory status
for p in dr-eggbot homelab-ops; do
  diff -rq -x .git ~/.hermes/profiles/$p/plugins/pstack builds/hermes/pstack && echo "$p matches"
  grep -n -A2 'enabled:' ~/.hermes/profiles/$p/config.yaml | grep -n pstack
done
```
Expected:
- status shows `installed: dr-eggbot@<main sha>, homelab-ops@<main sha>`
- both profiles print `matches`
- pstack is still listed under `enabled`

If the profile's `.install-metadata.json` file appears among the `diff` lines, ignore it. If pstack is no longer enabled, run `hermes -p <p> plugins enable pstack`.

---

### Task 10: push the factory and run a final check

- [ ] **Step 1: Run the whole suite from the renamed folder.** Run `python3 -m unittest discover -s tests -v`. Expected: all OK.

- [ ] **Step 2: Push.** Run `git push -q origin main`, then `gh repo view scotu/agent-plugin-factory --json url`.

- [ ] **Step 3: Check a fresh clone.**

```bash
S=$(mktemp -d) && cd "$S" && git clone -q git@github.com:scotu/agent-plugin-factory.git && cd agent-plugin-factory
python3 -m unittest discover -s tests && python3 -m factory status
```
Expected: the tests pass, and status prints `pstack/hermes: not cloned (run sync)`. Then `rm -rf "$S"`. Do not run `sync` here, because it would push a build with a different `FACTORY` stamp.

- [ ] **Step 4: Stop.** Pulling upstream 0.15.6 into pstack (`python3 -m factory sync pstack --install`) is a separate step and needs explicit approval.
