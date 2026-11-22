import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MARKETPLACE_PATH = REPOSITORY_ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_PATH = REPOSITORY_ROOT / "plugins" / "agent-fleet" / ".claude-plugin" / "plugin.json"

marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
plugin = json.loads(PLUGIN_PATH.read_text(encoding="utf-8"))
entries = [entry for entry in marketplace["plugins"] if entry["name"] == plugin["name"]]

if len(entries) != 1:
    raise SystemExit(f"Expected one marketplace entry for {plugin['name']}, found {len(entries)}")
if entries[0].get("version") != plugin.get("version"):
    raise SystemExit(
        f"Version mismatch: marketplace has {entries[0].get('version')!r}, "
        f"plugin manifest has {plugin.get('version')!r}"
    )

print(f"Release metadata synchronized: {plugin['name']} {plugin['version']}")
