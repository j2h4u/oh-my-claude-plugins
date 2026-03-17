<!-- Source: https://code.claude.com/docs/en/plugin-marketplaces -->
# Create and distribute a plugin marketplace

Build plugin marketplaces to distribute Claude Code extensions with centralized discovery, version tracking, and automatic updates.

## Overview

Creating a marketplace involves:
1. **Create plugins** with commands, agents, hooks, MCP/LSP servers
2. **Create `marketplace.json`** listing plugins and their sources
3. **Host on GitHub/GitLab** or other git provider
4. **Share with users** via `/plugin marketplace add`

Users update with `/plugin marketplace update`

## Quick Start: Local Marketplace

```bash
mkdir -p my-marketplace/.claude-plugin/{plugins/review-plugin/{.claude-plugin,skills/review}}
```

**SKILL.md** (`my-marketplace/plugins/review-plugin/skills/review/SKILL.md`):
```markdown
---
description: Review code for bugs, security, and performance
disable-model-invocation: true
---
Review selected/recent code for bugs, security, performance, readability.
```

**plugin.json** (`.claude-plugin/plugin.json`):
```json
{
  "name": "review-plugin",
  "description": "Adds /review skill for code reviews",
  "version": "1.0.0"
}
```

**marketplace.json** (`.claude-plugin/marketplace.json`):
```json
{
  "name": "my-plugins",
  "owner": { "name": "Your Name" },
  "plugins": [{
    "name": "review-plugin",
    "source": "./plugins/review-plugin",
    "description": "Adds /review skill"
  }]
}
```

**Install & test**:
```shell
/plugin marketplace add ./my-marketplace
/plugin install review-plugin@my-plugins
/review  # Try the skill
```

## Marketplace Schema

**Required fields:**
| Field | Type | Example |
|-------|------|---------|
| `name` | string | `"acme-tools"` (kebab-case) |
| `owner` | object | `{ "name": "DevTools Team", "email": "..." }` |
| `plugins` | array | See plugin entries below |

**Optional metadata:**
- `metadata.description` - marketplace description
- `metadata.version` - marketplace version
- `metadata.pluginRoot` - base dir for relative paths (e.g., `"./plugins"`)

**Reserved names** (blocked): `claude-code-marketplace`, `claude-code-plugins`, `claude-plugins-official`, `anthropic-marketplace`, `anthropic-plugins`, `agent-skills`, `life-sciences`, and impersonating names

## Plugin Entries

**Required fields:**
| Field | Type | Notes |
|-------|------|-------|
| `name` | string | kebab-case, public-facing |
| `source` | string\|object | Where to fetch plugin |

**Optional metadata fields:**
- `description`, `version`, `author`, `homepage`, `repository`, `license`, `keywords`, `category`, `tags`
- `strict` (boolean) - Controls `plugin.json` authority (default: true)

**Component configuration:**
- `commands`, `agents`, `hooks`, `mcpServers`, `lspServers` - Custom paths or configurations

## Plugin Sources

| Source | Type | Fields | Notes |
|--------|------|--------|-------|
| Relative path | string | — | Must start with `./` |
| `github` | object | `repo`, `ref?`, `sha?` | `owner/repo` format |
| `url` | object | `url`, `ref?`, `sha?` | Full git URL (`.git` required) |
| `git-subdir` | object | `url`, `path`, `ref?`, `sha?` | Sparse clone for monorepos |
| `npm` | object | `package`, `version?`, `registry?` | npm install |
| `pip` | object | `package`, `version?`, `registry?` | pip install |

**Examples:**

GitHub:
```json
{ "name": "plugin", "source": { "source": "github", "repo": "owner/repo", "ref": "v2.0.0" } }
```

Git URL:
```json
{ "name": "plugin", "source": { "source": "url", "url": "https://gitlab.com/team/plugin.git" } }
```

Git subdirectory:
```json
{ "name": "plugin", "source": { "source": "git-subdir", "url": "https://github.com/org/monorepo.git", "path": "tools/plugin" } }
```

npm:
```json
{ "name": "plugin", "source": { "source": "npm", "package": "@org/plugin", "version": "2.1.0" } }
```

**Note:** Relative paths only work via Git. URL-based distribution requires `github`, `npm`, or `git-subdir` sources.

## Hosting & Distribution

**GitHub (recommended):**
1. Create repo, add `.claude-plugin/marketplace.json`
2. Users add: `/plugin marketplace add owner/repo`

**Other git services:** Users add with full URL: `/plugin marketplace add https://gitlab.com/company/plugins.git`

**Private repositories:**
- Manual: Uses existing git credentials
- Auto-updates: Set `GITHUB_TOKEN`, `GITLAB_TOKEN`, or `BITBUCKET_TOKEN` environment variable

**Test locally:**
```shell
/plugin marketplace add ./my-local-marketplace
/plugin install test-plugin@my-local-marketplace
```

**Require marketplace for team** (`.claude/settings.json`):
```json
{
  "extraKnownMarketplaces": {
    "company-tools": {
      "source": { "source": "github", "repo": "your-org/claude-plugins" }
    }
  },
  "enabledPlugins": {
    "formatter@company-tools": true
  }
}
```

## Managed Marketplace Restrictions

Use `strictKnownMarketplaces` in managed settings to restrict which marketplaces users can add:

```json
{
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "acme-corp/approved-plugins" },
    { "source": "url", "url": "https://plugins.example.com/marketplace.json" }
  ]
}
```

Lock down completely: `"strictKnownMarketplaces": []`

Pattern matching:
```json
{ "source": "hostPattern", "hostPattern": "^github\\.example\\.com$" }
{ "source": "pathPattern", "pathPattern": "^/opt/approved/" }
```

## Release Channels

Set up "stable" and "latest" by pointing to different refs. **Important:** Each ref must have a different `version` in `plugin.json`.

```json
{
  "name": "stable-tools",
  "plugins": [{
    "name": "formatter",
    "source": { "source": "github", "repo": "acme/formatter", "ref": "stable" }
  }]
}
```

Assign channels to user groups via managed settings.

## Validation & Testing

```bash
claude plugin validate .           # Validate syntax
/plugin validate .                 # From Claude Code
/plugin marketplace add ./path     # Add for testing
/plugin install plugin@marketplace # Test installation
```

**Common errors:**
| Error | Solution |
|-------|----------|
| `File not found: marketplace.json` | Create at `.claude-plugin/marketplace.json` |
| `Invalid JSON syntax` | Check for missing/extra commas |
| `Duplicate plugin name` | Ensure unique names |
| `Path traversal not allowed` | No `..` in paths |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Marketplace not loading | Verify URL, check `.claude-plugin/marketplace.json` exists, validate JSON |
| Private repo auth fails | Set `GITHUB_TOKEN`/`GITLAB_TOKEN`, verify git credentials work |
| Git timeout (>120s) | Set `CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS=300000` (5 min) |
| Relative paths fail in URL marketplaces | Use GitHub/npm/git-subdir sources instead, or host via Git |
| Files not found after install | Plugins are cached; avoid `../` paths. Use symlinks. See [Plugin caching](/en/plugins-reference#plugin-caching-and-file-resolution) |

## Key Notes

- **Plugin caching:** Plugins copied to cache; can't reference files outside plugin dir. Use symlinks.
- **Marketplace vs plugin sources:** Different concepts; can be in different repos with independent pinning
- **Strict mode:** `true` = `plugin.json` authority (default); `false` = marketplace entry is entire definition
- **Version resolution:** Set in marketplace entry for relative paths; in plugin manifest for other sources

## See Also

- [Discover and install plugins](/en/discover-plugins)
- [Create plugins](/en/plugins)
- [Plugins reference](/en/plugins-reference)
- [Plugin settings](/en/settings#plugin-settings)
