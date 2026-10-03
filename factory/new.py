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
