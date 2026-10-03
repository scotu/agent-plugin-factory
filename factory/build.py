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
        if git(clone, "branch", "--show-current") == "upstream":
            raise SyncError(f"{clone} is on `upstream` with a partial build (an interrupted sync); discard it with "
                            f"`git -C {clone} reset --hard && git -C {clone} clean -fdx && git -C {clone} switch main`")
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
        # Everything from wiping the tree to the build commit is rolled back on any failure, including
        # SystemExit from a hook and Ctrl-C, so the clone is never left on `upstream` half-built.
        try:
            _empty(clone)
            port(src, clone, ctx)
            if not (clone / manifest).exists():
                raise HookError(f"hook produced no {manifest}")
            (clone / "UPSTREAM").write_text(f"repo: {plugin.repo}\npath: {plugin.path}\nref: {ref}\ncommit: {sha}\n")
            (clone / "FACTORY").write_text(factory_stamp(root))
            label = f"{name} {ctx.version}" if ctx.version else name
            git(clone, "add", "-A")
            if is_dirty(clone):
                git(clone, "commit", "-q", "-m", f"{label} @ {sha[:12]}")
        except BaseException as exc:
            git(clone, "reset", "-q", "--hard", before)
            git(clone, "clean", "-qfdx")
            git(clone, "switch", "-q", "main")
            if isinstance(exc, KeyboardInterrupt):
                raise
            raise HookError(f"build of {name}/{target} failed: {exc}") from exc
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
