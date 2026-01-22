# TODO

## Interactive Installer

Create an interactive installer script that:

1. **Auto-detects installed AI coding agents:**
   - Claude Code (`claude` CLI)
   - Antigravity
   - OpenCode (`opencode` CLI)

2. **Shows available plugins** with descriptions

3. **Lets user select** which plugins to install (checkboxes)

4. **Installs to correct location** based on detected agent:
   - Claude Code: `~/.claude/plugins/` or project `.claude-plugin/`
   - OpenCode: respective config location
   - Antigravity: respective config location

5. **Configures marketplace.json** automatically if supported

### Implementation ideas

- Bash script with `dialog` or `gum` for TUI
- Or simple interactive prompts with `read`
- Detect agents: `command -v claude`, `command -v opencode`, etc.
