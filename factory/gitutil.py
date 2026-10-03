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
