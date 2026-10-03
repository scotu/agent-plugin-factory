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
