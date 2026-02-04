#!/usr/bin/env python3
"""
Plugin version synchronization tool for oh-my-claude-plugins marketplace.

Syncs versions from local plugin.json files to marketplace.json.
Safe to run without arguments — shows help and usage.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MARKETPLACE_PATH = REPO_ROOT / '.claude-plugin' / 'marketplace.json'


def print_help() -> None:
    """Print usage information."""
    print('''
sync-versions.py — Plugin version synchronization tool

USAGE:
    ./scripts/sync-versions.py [COMMAND]

COMMANDS:
    --sync      Sync versions from local plugin.json to marketplace.json
                This is the main command. Bumps marketplace version if changes detected.

    --check     Validate only, no changes. Exit 1 if out of sync.
                Use in CI to ensure versions are synchronized.

    --list      Show all plugins with their versions.

    --help, -h  Show this help message.

WORKFLOW:
    1. Update version in local <plugin>/.claude-plugin/plugin.json
    2. Run: ./scripts/sync-versions.py --sync
    3. Commit both files

PRE-COMMIT HOOK:
    Add to .git/hooks/pre-commit:
        ./scripts/sync-versions.py --sync && git add .claude-plugin/marketplace.json

VALIDATION:
    The tool also checks for:
    - Missing plugins (in local but not in marketplace)
    - Invalid source paths
    - Duplicate plugin names
'''.strip())


def find_local_plugins() -> dict[str, dict]:
    """Find all local plugin.json files and return {name: {version, path, source_dir}}."""
    plugins = {}

    for plugin_json in REPO_ROOT.glob('*/.claude-plugin/plugin.json'):
        try:
            data = json.loads(plugin_json.read_text())
            name = data.get('name')
            version = data.get('version')
            source_dir = plugin_json.parent.parent.name

            if name and version:
                plugins[name] = {
                    'version': version,
                    'path': plugin_json,
                    'source_dir': source_dir,
                }
        except (json.JSONDecodeError, KeyError) as e:
            print(f'Warning: Failed to parse {plugin_json}: {e}')

    return plugins


def load_marketplace() -> dict:
    """Load marketplace.json."""
    return json.loads(MARKETPLACE_PATH.read_text())


def save_marketplace(data: dict) -> None:
    """Save marketplace.json with consistent formatting."""
    MARKETPLACE_PATH.write_text(json.dumps(data, indent=2) + '\n')


def bump_patch_version(version: str) -> str:
    """Bump patch version: 1.2.3 -> 1.2.4."""
    parts = version.split('.')
    if len(parts) == 3:
        parts[2] = str(int(parts[2]) + 1)
    return '.'.join(parts)


def validate_plugins(local_plugins: dict, marketplace: dict) -> list[str]:
    """Validate plugins and return list of issues."""
    issues = []
    marketplace_plugins = {p['name']: p for p in marketplace.get('plugins', [])}

    # Check for missing plugins (local but not in marketplace)
    for name in local_plugins:
        if name not in marketplace_plugins:
            issues.append(f'Missing in marketplace: {name}')

    # Check for orphaned plugins (in marketplace but no local)
    for name in marketplace_plugins:
        if name not in local_plugins:
            issues.append(f'Orphaned in marketplace (no local plugin.json): {name}')

    # Check source paths
    for plugin in marketplace.get('plugins', []):
        source = plugin.get('source', '')
        source_path = REPO_ROOT / source.lstrip('./')
        if not source_path.is_dir():
            issues.append(f"Invalid source path for {plugin['name']}: {source}")

    # Check for duplicate names
    names = [p['name'] for p in marketplace.get('plugins', [])]
    seen = set()
    for name in names:
        if name in seen:
            issues.append(f'Duplicate plugin name: {name}')
        seen.add(name)

    return issues


def find_version_mismatches(local_plugins: dict, marketplace: dict) -> list[dict]:
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


def cmd_list() -> int:
    """Show all plugins with versions."""
    local_plugins = find_local_plugins()
    marketplace = load_marketplace()
    marketplace_plugins = {p['name']: p for p in marketplace.get('plugins', [])}

    print(f"{'PLUGIN':<25} {'LOCAL':<12} {'MARKETPLACE':<12} {'STATUS'}")
    print('-' * 60)

    all_names = sorted(set(local_plugins.keys()) | set(marketplace_plugins.keys()))

    for name in all_names:
        local_ver = local_plugins.get(name, {}).get('version', '-')
        mp_ver = marketplace_plugins.get(name, {}).get('version', '-')

        if local_ver == '-':
            status = 'orphaned'
        elif mp_ver == '-':
            status = 'missing'
        elif local_ver != mp_ver:
            status = 'out of sync'
        else:
            status = 'ok'

        print(f'{name:<25} {local_ver:<12} {mp_ver:<12} {status}')

    mp_version = marketplace.get('metadata', {}).get('version', '?')
    print(f'\nMarketplace version: {mp_version}')

    return 0


def cmd_check() -> int:
    """Validate only, exit 1 if issues found."""
    local_plugins = find_local_plugins()
    marketplace = load_marketplace()

    issues = validate_plugins(local_plugins, marketplace)
    mismatches = find_version_mismatches(local_plugins, marketplace)

    if issues:
        print('Validation issues:')
        for issue in issues:
            print(f'  - {issue}')

    if mismatches:
        print('Version mismatches:')
        for m in mismatches:
            print(f"  - {m['name']}: marketplace={m['marketplace_version']} local={m['local_version']}")

    if issues or mismatches:
        print('\nRun ./scripts/sync-versions.py --sync to fix version mismatches.')
        return 1

    print('All checks passed.')
    return 0


def cmd_sync() -> int:
    """Sync versions from local to marketplace."""
    local_plugins = find_local_plugins()
    marketplace = load_marketplace()

    # Validate first
    issues = validate_plugins(local_plugins, marketplace)
    if issues:
        print('Validation issues (fix manually):')
        for issue in issues:
            print(f'  - {issue}')
        return 1

    # Find and apply mismatches
    mismatches = find_version_mismatches(local_plugins, marketplace)

    if not mismatches:
        print('All versions already in sync.')
        return 0

    print('Syncing versions:')
    for m in mismatches:
        print(f"  {m['name']}: {m['marketplace_version']} -> {m['local_version']}")

    # Update marketplace
    for plugin in marketplace.get('plugins', []):
        name = plugin.get('name')
        if name in local_plugins:
            plugin['version'] = local_plugins[name]['version']

    # Bump marketplace version
    old_version = marketplace.get('metadata', {}).get('version', '1.0.0')
    new_version = bump_patch_version(old_version)
    marketplace['metadata']['version'] = new_version
    print(f'\nMarketplace version: {old_version} -> {new_version}')

    save_marketplace(marketplace)
    print(f'Updated {MARKETPLACE_PATH}')

    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h'):
        print_help()
        return 0

    cmd = sys.argv[1]

    if cmd == '--list':
        return cmd_list()
    elif cmd == '--check':
        return cmd_check()
    elif cmd == '--sync':
        return cmd_sync()
    else:
        print(f'Unknown command: {cmd}')
        print('Run with --help for usage.')
        return 1


if __name__ == '__main__':
    sys.exit(main())
