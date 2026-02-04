#!/usr/bin/env python3
"""
Sync plugin versions from local plugin.json files to marketplace.json.

Usage:
    ./scripts/sync-versions.py          # Check and fix if needed
    ./scripts/sync-versions.py --check  # Check only, exit 1 if out of sync
    ./scripts/sync-versions.py --fix    # Fix without prompting
"""

import json
import sys
from pathlib import Path


def find_local_plugins(repo_root: Path) -> dict[str, dict]:
    """Find all local plugin.json files and return {name: {version, path}}."""
    plugins = {}

    for plugin_json in repo_root.glob('*/.claude-plugin/plugin.json'):
        try:
            data = json.loads(plugin_json.read_text())
            name = data.get('name')
            version = data.get('version')

            if name and version:
                plugins[name] = {
                    'version': version,
                    'path': plugin_json,
                }
        except (json.JSONDecodeError, KeyError) as e:
            print(f'Warning: Failed to parse {plugin_json}: {e}')

    return plugins


def load_marketplace(repo_root: Path) -> tuple[dict, Path]:
    """Load marketplace.json and return (data, path)."""
    marketplace_path = repo_root / '.claude-plugin' / 'marketplace.json'
    data = json.loads(marketplace_path.read_text())
    return data, marketplace_path


def find_version_mismatches(
    local_plugins: dict[str, dict],
    marketplace: dict,
) -> list[dict]:
    """Find plugins where local version differs from marketplace version."""
    mismatches = []

    marketplace_plugins = {p['name']: p for p in marketplace.get('plugins', [])}

    for name, local in local_plugins.items():
        if name in marketplace_plugins:
            mp_version = marketplace_plugins[name].get('version')
            if mp_version != local['version']:
                mismatches.append({
                    'name': name,
                    'local_version': local['version'],
                    'marketplace_version': mp_version,
                })

    return mismatches


def bump_patch_version(version: str) -> str:
    """Bump patch version: 1.2.3 -> 1.2.4."""
    parts = version.split('.')
    if len(parts) == 3:
        parts[2] = str(int(parts[2]) + 1)
    return '.'.join(parts)


def sync_versions(
    marketplace: dict,
    local_plugins: dict[str, dict],
    mismatches: list[dict],
) -> bool:
    """Update marketplace with local versions. Returns True if changes made."""
    if not mismatches:
        return False

    # Update plugin versions
    for plugin in marketplace.get('plugins', []):
        name = plugin.get('name')
        if name in local_plugins:
            plugin['version'] = local_plugins[name]['version']

    # Bump marketplace metadata version
    old_version = marketplace.get('metadata', {}).get('version', '1.0.0')
    new_version = bump_patch_version(old_version)
    marketplace['metadata']['version'] = new_version

    return True


def main() -> int:
    check_only = '--check' in sys.argv
    fix_mode = '--fix' in sys.argv

    repo_root = Path(__file__).parent.parent

    # Find local plugins
    local_plugins = find_local_plugins(repo_root)
    print(f'Found {len(local_plugins)} local plugins')

    # Load marketplace
    marketplace, marketplace_path = load_marketplace(repo_root)

    # Find mismatches
    mismatches = find_version_mismatches(local_plugins, marketplace)

    if not mismatches:
        print('All versions are in sync!')
        return 0

    # Report mismatches
    print(f'\nFound {len(mismatches)} version mismatch(es):')
    for m in mismatches:
        print(f"  {m['name']}: {m['marketplace_version']} -> {m['local_version']}")

    if check_only:
        print('\nRun without --check to fix.')
        return 1

    # Sync versions
    old_mp_version = marketplace.get('metadata', {}).get('version')
    sync_versions(marketplace, local_plugins, mismatches)
    new_mp_version = marketplace.get('metadata', {}).get('version')

    print(f'\nMarketplace version: {old_mp_version} -> {new_mp_version}')

    if not fix_mode:
        response = input('Apply changes? [y/N] ')
        if response.lower() != 'y':
            print('Aborted.')
            return 1

    # Write updated marketplace
    marketplace_path.write_text(
        json.dumps(marketplace, indent=2) + '\n'
    )
    print(f'Updated {marketplace_path}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
