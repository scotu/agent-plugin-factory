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
    path: str | None = None  # upstream subdir for this target, when it differs from [upstream] path
    ref: str | None = None
    marketplace: str | None = None  # Claude Code marketplace that installs this target's build


@dataclass(frozen=True)
class Plugin:
    name: str
    dir: Path
    repo: str
    path: str
    ref: str
    targets: dict[str, Target]

    def source(self, target: str) -> tuple[str, str]:
        """The upstream (path, ref) this target builds from."""
        t = self.targets[target]
        return (self.path if t.path is None else t.path, t.ref or self.ref)


def load(root: Path, name: str) -> Plugin:
    plugin_dir = root / "plugins" / name
    file = plugin_dir / "plugin.toml"
    if not file.exists():
        raise ConfigError(f"unknown plugin '{name}': {file} not found")
    data = tomllib.loads(file.read_text())
    try:
        up = data["upstream"]
        targets = {t: Target(t, v["build_repo"], v.get("plugin_key", name),
                             v["path"].strip("/") if "path" in v else None, v.get("ref"), v.get("marketplace"))
                   for t, v in data["targets"].items()}
        return Plugin(name, plugin_dir, up["repo"], up.get("path", "").strip("/"), up.get("ref", "main"), targets)
    except KeyError as exc:
        raise ConfigError(f"{file}: missing {exc}") from None


def names(root: Path) -> list[str]:
    return sorted(p.parent.name for p in (root / "plugins").glob("*/plugin.toml"))
