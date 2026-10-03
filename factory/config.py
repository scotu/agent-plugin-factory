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
