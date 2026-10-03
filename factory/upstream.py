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
