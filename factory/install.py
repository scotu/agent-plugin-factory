"""Where a build is installed: Hermes profiles that installed it from the local build clone (file://), and
Claude Code's own install records for a build published as a marketplace."""
import json
from pathlib import Path

DEFAULT_PROFILES = Path.home() / ".hermes" / "profiles"
DEFAULT_CC_PLUGINS = Path.home() / ".claude" / "plugins" / "installed_plugins.json"


def installed(profiles_dir: Path, plugin_key: str, clone: Path) -> list[tuple[str, str]]:
    source = clone.resolve().as_uri()
    found = []
    for meta in sorted(profiles_dir.glob("*/plugins/.install-metadata.json")):
        entry = json.loads(meta.read_text()).get(plugin_key)
        if isinstance(entry, dict) and entry.get("source") == source:
            found.append((meta.parents[1].name, str(entry.get("revision", ""))))
    return found



def claude_code_installed(plugins_json: Path, plugin_id: str) -> list[tuple[str, str]]:
    """(scope, gitCommitSha) for each Claude Code install of `<plugin>@<marketplace>`. A plugin that settings enable
    (enabledPlugins + extraKnownMarketplaces) has no install record, so fall back to the live cache folder
    `cache/<marketplace>/<plugin>/<version>/`, whose name is the commit when the manifest has no version."""
    try:
        records = json.loads(plugins_json.read_text()).get("plugins", {}) if plugins_json.exists() else {}
    except ValueError:
        records = {}
    entries = records.get(plugin_id, []) if isinstance(records, dict) else []
    found = [(str(e.get("scope", "")), str(e.get("gitCommitSha", ""))) for e in entries if isinstance(e, dict)]
    if found:
        return found
    name, _, marketplace = plugin_id.partition("@")
    cache = plugins_json.parent / "cache" / marketplace / name
    live = [d for d in cache.iterdir() if d.is_dir() and not (d / ".orphaned_at").exists()] if cache.is_dir() else []
    return [("cache", max(live, key=lambda d: d.stat().st_mtime).name)] if live else []
