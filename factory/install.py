"""Hermes profiles that installed a plugin from a local build clone (file://)."""
import json
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

