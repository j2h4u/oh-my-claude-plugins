# Scripts

Developer utilities for maintaining the marketplace.

## sync-versions.py

**Problem:** Plugin versions live in two places — local `<plugin>/.claude-plugin/plugin.json` and the central `.claude-plugin/marketplace.json`. Keeping them in sync manually is error-prone.

**Solution:** This script reads versions from local plugin.json files and updates marketplace.json automatically. It also validates the marketplace structure (missing plugins, broken paths, duplicates).

**Workflow:**
1. Bump version in local plugin.json when you change plugin code
2. Run `./scripts/sync-versions.py --sync`
3. Commit both files

Run without arguments to see available commands.
