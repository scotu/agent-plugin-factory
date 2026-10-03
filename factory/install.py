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
