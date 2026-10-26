"""Create a plugin folder from templates and its build repo (upstream: empty init commit; main: ledger + README)."""
import shutil
import subprocess
from pathlib import Path

from . import config
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


def _gh(*args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise ConfigError("the GitHub CLI `gh` is not installed; pass --remote with an existing empty repo") from None


def _init_build_repo(clone: Path, remote: str, values: dict) -> None:
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


def new(root: Path, name: str, target: str, upstream_spec: str, remote: str, *,
        github_repo: str | None = None, public: bool = True) -> Path:
    """Create the build repo first and the plugin folder last, so a failure leaves nothing local behind
    and the command can simply be run again (an existing GitHub repo is reused)."""
    plugin_dir = root / "plugins" / name
    clone = clone_path(root, name, target)
    for path in (plugin_dir, clone):
        if path.exists():
            raise ConfigError(f"{path} already exists")
    repo, _, sub = upstream_spec.partition("#")
    values = dict(name=name, target=target, repo=repo, path=sub.strip("/"), remote=remote)

    if github_repo:
        try:
            _gh("repo", "view", github_repo)
        except subprocess.CalledProcessError:
            _gh("repo", "create", github_repo, "--public" if public else "--private",
                "--description", f"{name} built for {target} by agent-plugin-factory")
    try:
        _init_build_repo(clone, remote, values)
    except BaseException:
        shutil.rmtree(clone, ignore_errors=True)
        raise
    if github_repo:
        _gh("repo", "edit", github_repo, "--default-branch", "main")

    (plugin_dir / target).mkdir(parents=True)
    (plugin_dir / "plugin.toml").write_text(_fill("plugin.toml", **values))
    (plugin_dir / target / "port.py").write_text(_fill("port.py", **values))
    return plugin_dir


def add_target(root: Path, name: str, target: str, remote: str, *, github_repo: str | None = None,
               public: bool = True, path: str | None = None, ref: str | None = None,
               marketplace: str | None = None) -> Path:
    """Give an existing plugin a new target: create its build repo, then append the target to plugin.toml and
    write a stub port hook if the target has none. Like `new`, the build repo comes first so a failure leaves
    the plugin folder untouched."""
    plugin = config.load(root, name)
    if target in plugin.targets:
        raise ConfigError(f"plugin '{name}' already has target '{target}'")
    clone = clone_path(root, name, target)
    if clone.exists():
        raise ConfigError(f"{clone} already exists")
    values = dict(name=name, target=target, repo=plugin.repo, path=path if path is not None else plugin.path,
                  remote=remote)
    if github_repo:
        try:
            _gh("repo", "view", github_repo)
        except subprocess.CalledProcessError:
            _gh("repo", "create", github_repo, "--public" if public else "--private",
                "--description", f"{name} built for {target} by agent-plugin-factory")
    try:
        _init_build_repo(clone, remote, values)
    except BaseException:
        shutil.rmtree(clone, ignore_errors=True)
        raise
    if github_repo:
        _gh("repo", "edit", github_repo, "--default-branch", "main")

    block = f'\n[targets.{target}]\nbuild_repo = "{remote}"\nplugin_key = "{name}"\n'
    block += "".join(f'{key} = "{value}"\n' for key, value in
                     (("path", path), ("ref", ref), ("marketplace", marketplace)) if value is not None)
    toml = plugin.dir / "plugin.toml"
    toml.write_text(toml.read_text().rstrip("\n") + "\n" + block)
    hook = plugin.dir / target / "port.py"
    if not hook.exists():
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(_fill("port.py", **values))
    return plugin.dir
