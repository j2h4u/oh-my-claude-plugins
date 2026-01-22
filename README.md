# Oh My Claude Plugins

**Curated collection of Claude Code plugins for everyday development.**

Skills, agents, and hooks that make Claude Code smarter about your workflow — from coding standards to git automation.

## Quick Start

```bash
# Add marketplace
/plugin marketplace add j2h4u/oh-my-claude-plugins

# Install what you need
/plugin install coding-standards@oh-my-claude-plugins
```

Or browse interactively: `/plugin` → `Browse and install plugins` → `oh-my-claude-plugins`

## Available Plugins

### coding-standards

Code quality and development philosophy.

| Skill | Triggers | Description |
|-------|----------|-------------|
| dignified-bash | Writing bash scripts | Strict mode, shellcheck, defensive patterns |
| dignified-python | Writing Python code | LBYL philosophy, version-aware (3.10-3.13), Click CLI |
| kaizen | Code quality discussions | Continuous improvement, poka-yoke, YAGNI |
| software-architecture | Architecture decisions | Clean Architecture & DDD principles *(incomplete)* |

### git-tools

Git workflows and GitHub integration.

| Skill | Triggers | Description |
|-------|----------|-------------|
| changelog-generator | "generate changelog" | Transform commits into user-friendly changelogs |
| gh | GitHub CLI usage | PR management, GraphQL API, Projects V2 |
| git-workflow-manager | Commits, releases | Conventional commits, semantic versioning |

### web-dev

Frontend development.

| Skill | Triggers | Description |
|-------|----------|-------------|
| vercel-react-best-practices | React/Next.js code | 45 performance rules: waterfalls, bundles, SSR |
| web-artifacts-builder | "create artifact" | Build React artifacts for Claude.ai |
| web-design-guidelines | UI review | Vercel Web Interface Guidelines *(incomplete)* |

### docs

Documentation creation.

| Skill | Triggers | Description |
|-------|----------|-------------|
| doc-coauthoring | "help write doc" | Collaborative workflow: gathering, refinement, reader testing |
| readme-generator | "write README" | README best practices by project type |

### devops

System administration.

| Skill | Triggers | Description |
|-------|----------|-------------|
| linux-sysadmin | Linux admin tasks | Debian/Ubuntu: systemd, permissions, packages |

### claude-code-meta

Claude Code tooling and meta-skills.

| Skill | Triggers | Description |
|-------|----------|-------------|
| cli-skill-creator | "create skill for CLI" | Meta-skill for creating CLI tool skills |
| mcp-builder | "build MCP server" | MCP server development: Python, Node.js |
| claude-md-redirect | CLAUDE.md operations | Redirect to AGENTS.md with PostToolUse hook |
| claude-md-writer | "write CLAUDE.md" | CLAUDE.md best practices: size limits, 3-tier docs |
| opencode-config | OpenCode CLI setup | Custom providers, model selection |

**Utility:** `statusline` — Custom statusline showing costs & context usage. Install via `@"statusline-setup"` agent.

### productivity

Analysis tools.

| Skill | Triggers | Description |
|-------|----------|-------------|
| meeting-insights-analyzer | "analyze meeting" | Communication patterns, speaking ratios |

### agents

Custom agents for code tasks.

| Agent | Triggers | Description |
|-------|----------|-------------|
| python-code-reviewer | "review Python code" | READ-ONLY analysis, creates issue report |
| python-quick-fixer | "fix Python issues" | Batch fixes from issue list |
| quick-worker | "do this task" | Fast executor for mechanical tasks |

## Alternative Installation

Use as local plugin directory (development mode):

```bash
claude --plugin-dir /path/to/oh-my-claude-plugins
```

## Requirements

- Claude Code CLI
- Git (for version control features)

## Status Legend

| Marker | Meaning |
|--------|---------|
| *(incomplete)* | Needs work |

## License

Individual items may have their own licenses. Check each directory.
