# fix-enabled-plugins

Ensures all installed Claude Code plugins are explicitly enabled in `settings.json`.

## The problem

Older Claude Code versions loaded all installed plugins automatically without any extra configuration. Some newer versions require plugins to be explicitly listed in the `enabledPlugins` map in `~/.claude/settings.json`. If a plugin is installed but not listed there, it may silently fail to load — skills and agents simply don't appear in the session.

## Usage

```bash
python3 fix-enabled-plugins.py
```

The script:

1. Reads installed plugins from `~/.claude/plugins/installed_plugins.json`
2. Compares with `enabledPlugins` in `~/.claude/settings.json`
3. Shows a diff — what's missing, what's stale
4. Creates a timestamped backup of `settings.json`
5. Syncs `enabledPlugins` to match installed plugins

Safe to run multiple times. If everything is already in sync, it exits with no changes.

Restart Claude Code after running.

## Example output

```
Installed plugins: 19
Currently enabled: 17

Not enabled (2):
  + programming-languages@oh-my-claude-plugins
  + vibecoding@oh-my-claude-plugins

Backup: /home/user/.claude/settings.json.20260315143022.bak
Updated /home/user/.claude/settings.json
Enabled plugins: 19

Restart Claude Code for changes to take effect.
```
