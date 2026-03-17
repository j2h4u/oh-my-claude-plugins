<!-- Source: https://code.claude.com/docs/en/plugins-reference -->
# Plugins reference

> Complete technical reference for Claude Code plugin system, including schemas, CLI commands, and component specifications.

## Plugin Components

### Skills
- **Location**: `skills/` or `commands/` directory
- **Format**: Directories with `SKILL.md` or simple markdown files
- Auto-discovered and invoked by Claude based on context

### Agents
- **Location**: `agents/` directory
- **Format**: Markdown with frontmatter (name, description)
- Specialized subagents invoked automatically or manually

### Hooks
- **Location**: `hooks/hooks.json` or inline in `plugin.json`
- **Events**: PreToolUse, PostToolUse, PostToolUseFailure, PermissionRequest, UserPromptSubmit, Notification, Stop, SubagentStart, SubagentStop, SessionStart, SessionEnd, TeammateIdle, TaskCompleted, PreCompact
- **Types**: command, prompt, agent

### MCP Servers
- **Location**: `.mcp.json` or inline in `plugin.json`
- Start automatically when plugin enabled
- Integrate as standard tools

### LSP Servers
- **Location**: `.lsp.json` or inline in `plugin.json`
- Provides diagnostics, code navigation, language awareness
- **Required fields**: `command`, `extensionToLanguage`
- **Optional fields**: args, transport, env, initializationOptions, settings, workspaceFolder, timeouts, restartOnCrash, maxRestarts
- Must install language server binary separately

## Installation Scopes

| Scope | File | Use Case |
|-------|------|----------|
| user | `~/.claude/settings.json` | Personal plugins (default) |
| project | `.claude/settings.json` | Team plugins via version control |
| local | `.claude/settings.local.json` | Project-specific, gitignored |
| managed | Managed settings | Read-only plugins |

## Plugin Manifest (`plugin.json`)

**Required**: `name` (kebab-case)

**Metadata**: version, description, author, homepage, repository, license, keywords

**Component paths**: commands, agents, skills, hooks, mcpServers, outputStyles, lspServers (all optional, supplement defaults)

**Path rules**:
- Must be relative, start with `./`
- Supplement default directories (don't replace)
- Can specify arrays for multiple paths

**Environment variable**: `${CLAUDE_PLUGIN_ROOT}` (absolute plugin path)

## File Locations

| Component | Default | Purpose |
|-----------|---------|---------|
| Manifest | `.claude-plugin/plugin.json` | Metadata (optional) |
| Commands | `commands/` | Legacy skills |
| Agents | `agents/` | Subagents |
| Skills | `skills/` | Skills with SKILL.md |
| Hooks | `hooks/hooks.json` | Hook config |
| MCP | `.mcp.json` | MCP definitions |
| LSP | `.lsp.json` | Language servers |
| Settings | `settings.json` | Default config |

## CLI Commands

- `claude plugin install <plugin> [-s scope]`
- `claude plugin uninstall <plugin> [-s scope]`
- `claude plugin enable <plugin> [-s scope]`
- `claude plugin disable <plugin> [-s scope]`
- `claude plugin update <plugin> [-s scope]`

## Plugin Caching

- Marketplace plugins copied to `~/.claude/plugins/cache`
- Path traversal outside plugin root not supported
- Use symlinks for external dependencies

## Debugging

- `claude --debug` shows plugin loading details
- Common issues: Invalid JSON, wrong directory structure, non-executable scripts, missing language servers, absolute paths

## Versioning

**Format**: MAJOR.MINOR.PATCH
- Update version in `plugin.json` before distributing (triggers updates due to caching)
- Document changes in CHANGELOG.md
- Start at 1.0.0 for stable releases

**Critical**: Change version number to trigger plugin updates; code changes alone won't update cached plugins.
