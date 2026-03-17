<!-- Source: https://code.claude.com/docs/en/plugins -->
# Create plugins

**Quick links**: [Discover plugins](/en/discover-plugins) | [Plugins reference](/en/plugins-reference)

Extend Claude Code with custom skills, agents, hooks, and MCP servers via plugins—shareable across projects and teams.

## When to use plugins vs standalone configuration

| Approach | Skill names | Best for |
|----------|------------|----------|
| **Standalone** (`.claude/`) | `/hello` | Personal workflows, project-specific customizations |
| **Plugins** (`.claude-plugin/plugin.json`) | `/plugin-name:hello` | Team sharing, community distribution, versioned releases |

**Use standalone** for quick iteration on single projects. **Use plugins** for sharing, version control, and cross-project reuse.

## Quickstart

### Prerequisites
- Claude Code installed and authenticated
- Claude Code v1.0.33+ (`claude --version`)

### Create your first plugin

**Step 1: Create plugin directory**
```bash
mkdir my-first-plugin/.claude-plugin
```

**Step 2: Create manifest** (`my-first-plugin/.claude-plugin/plugin.json`)
```json
{
  "name": "my-first-plugin",
  "description": "A greeting plugin to learn the basics",
  "version": "1.0.0",
  "author": {"name": "Your Name"}
}
```

| Field | Purpose |
|-------|---------|
| `name` | Unique identifier and skill namespace |
| `description` | Shown in plugin manager |
| `version` | Uses semantic versioning |
| `author` | Optional attribution |

**Step 3: Add skill**
```bash
mkdir -p my-first-plugin/skills/hello
```

Create `my-first-plugin/skills/hello/SKILL.md`:
```markdown
---
description: Greet the user with a friendly message
disable-model-invocation: true
---

Greet the user warmly and ask how you can help them today.
```

**Step 4: Test plugin**
```bash
claude --plugin-dir ./my-first-plugin
/my-first-plugin:hello
```

**Step 5: Add skill arguments**

Update `SKILL.md`:
```markdown
---
description: Greet the user with a personalized message
---

Greet the user named "$ARGUMENTS" warmly...
```

Test: `/my-first-plugin:hello Alex`

## Plugin structure overview

⚠️ **Common mistake**: Only `plugin.json` goes in `.claude-plugin/`. All other directories go at plugin root.

| Directory | Purpose |
|-----------|---------|
| `.claude-plugin/` | Contains `plugin.json` manifest |
| `commands/` | Skills as Markdown files |
| `agents/` | Custom agent definitions |
| `skills/` | Agent Skills with `SKILL.md` files |
| `hooks/` | Event handlers in `hooks.json` |
| `.mcp.json` | MCP server configurations |
| `.lsp.json` | LSP server configurations |
| `settings.json` | Default settings when plugin enabled |

## Develop more complex plugins

### Add Skills
Create `skills/code-review/SKILL.md` with frontmatter:
```yaml
---
name: code-review
description: Reviews code for best practices. Use when reviewing code...
---

Checklist:
1. Code organization and structure
2. Error handling
3. Security concerns
4. Test coverage
```

### Add LSP servers
Create `.lsp.json`:
```json
{
  "go": {
    "command": "gopls",
    "args": ["serve"],
    "extensionToLanguage": {".go": "go"}
  }
}
```

### Ship default settings
Create `settings.json` to activate custom agents:
```json
{"agent": "security-reviewer"}
```

### Test plugins locally
```bash
claude --plugin-dir ./my-plugin
# Load multiple: --plugin-dir ./plugin-one --plugin-dir ./plugin-two
```

### Debug issues
1. Check directory structure (root-level, not in `.claude-plugin/`)
2. Test components individually
3. See [Debugging tools](/en/plugins-reference#debugging-and-development-tools)

### Share plugins
1. Add `README.md` with setup instructions
2. Use semantic versioning in `plugin.json`
3. Distribute via [plugin marketplaces](/en/plugin-marketplaces)
4. Submit to official marketplace: [claude.ai/settings/plugins/submit](https://claude.ai/settings/plugins/submit)

## Convert existing configurations to plugins

**Steps**:
1. Create `my-plugin/.claude-plugin/plugin.json` with name, description, version
2. Copy: `cp -r .claude/commands my-plugin/` (repeat for agents, skills)
3. Migrate hooks to `my-plugin/hooks/hooks.json`
4. Test: `claude --plugin-dir ./my-plugin`

| Standalone | Plugin |
|-----------|--------|
| Project-specific | Shareable via marketplaces |
| `.claude/commands/` | `plugin/commands/` |
| Manual sharing | `/plugin install` |

## Next steps

**Users**: [Discover plugins](/en/discover-plugins) | [Team marketplaces](/en/discover-plugins#configure-team-marketplaces)

**Developers**: [Create marketplaces](/en/plugin-marketplaces) | [Plugins reference](/en/plugins-reference) | [Skills](/en/skills) | [Subagents](/en/sub-agents) | [Hooks](/en/hooks) | [MCP](/en/mcp)
