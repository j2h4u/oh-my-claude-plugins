#!/usr/bin/env python3
"""Fix Claude Code plugin activation bug.

Some Claude Code versions require an explicit enabledPlugins map in settings.json
for plugins to load. Older versions loaded all installed plugins automatically,
but newer versions may silently skip plugins that aren't listed there. This
script syncs enabledPlugins in settings.json with installed_plugins.json,
ensuring every installed plugin is explicitly marked as enabled.

Safe to run multiple times — idempotent. Creates a timestamped backup of
settings.json before making changes.
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"
PLUGINS_PATH = CLAUDE_DIR / "plugins" / "installed_plugins.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = path.with_suffix(f".json.{timestamp}.bak")
    try:
        shutil.copy2(path, backup)
        return backup
    except OSError as e:
        print(f"WARNING: Could not create backup: {e}", file=sys.stderr)
        return None


def main() -> None:
    # --- diagnostics ---

    if not PLUGINS_PATH.exists():
        print(f"ERROR: {PLUGINS_PATH} not found.", file=sys.stderr)
        print("No plugins are installed. Nothing to fix.", file=sys.stderr)
        raise SystemExit(1)

    plugins_data = load_json(PLUGINS_PATH)
    plugins_dict = plugins_data.get("plugins", {})
    if not isinstance(plugins_dict, dict):
        print(f"ERROR: {PLUGINS_PATH} 'plugins' is not a dict.", file=sys.stderr)
        raise SystemExit(1)
    installed = list(plugins_dict.keys())

    if not installed:
        print(f"WARNING: {PLUGINS_PATH} exists but contains zero plugins.")
        print("Nothing to enable. Exiting.")
        raise SystemExit(0)

    if SETTINGS_PATH.exists():
        try:
            settings = load_json(SETTINGS_PATH)
        except json.JSONDecodeError as e:
            print(f"ERROR: {SETTINGS_PATH} is not valid JSON: {e}", file=sys.stderr)
            raise SystemExit(1)
    else:
        settings = {}
    enabled = settings.get("enabledPlugins", {})
    currently_enabled = [name for name, val in enabled.items() if val is True]

    print(f"Installed plugins: {len(installed)}")
    print(f"Currently enabled: {len(currently_enabled)}")
    print()

    # --- diff ---

    missing = [name for name in installed if enabled.get(name) is not True]
    extra = [name for name in enabled if name not in installed]

    if not missing and not extra:
        print("All installed plugins are already enabled. Nothing to do.")
        raise SystemExit(0)

    if missing:
        print(f"Not enabled ({len(missing)}):")
        for name in missing:
            print(f"  + {name}")

    if extra:
        print(f"\nEnabled but not installed ({len(extra)}) — will be removed:")
        for name in extra:
            print(f"  - {name}")

    print()

    # --- apply ---

    if extra:
        response = input(f"Remove {len(extra)} stale plugins? (y/n): ").strip().lower()
        if response != "y":
            print("Cancelled. No changes made.")
            raise SystemExit(0)

    backup = backup_file(SETTINGS_PATH)
    if backup:
        print(f"Backup: {backup}")

    settings["enabledPlugins"] = {name: True for name in installed}
    save_json(SETTINGS_PATH, settings)

    new_enabled = len(installed)
    print(f"Updated {SETTINGS_PATH}")
    print(f"Enabled plugins: {new_enabled}")
    print()
    print("Restart Claude Code for changes to take effect.")


if __name__ == "__main__":
    main()
