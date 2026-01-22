# Oh My Claude Plugins

**Curated collection of Claude Code skills for everyday development.**

Personal collection of Claude Code skills, agents, and plugins for everyday development.

## Quick Start

**Option 1: Use entire collection**
```bash
claude --plugin-dir /path/to/oh-my-claude-plugins
```

**Option 2: Add marketplace (after publishing to GitHub)**
```bash
# In Claude Code settings, add marketplace URL:
https://raw.githubusercontent.com/j2h4u/oh-my-claude-plugins/main/marketplace.json
```

**Option 3: Use single plugin**
```bash
claude --plugin-dir /path/to/oh-my-claude-plugins/git
```

## What's Included

### coding-standards

Code quality and development philosophy.

| Skill | Triggers | Description |
|-------|----------|-------------|
| dignified-bash | Writing bash scripts | Strict mode, shellcheck, defensive patterns, variable conventions |
| dignified-python | Writing Python code | LBYL philosophy, version-aware (3.10-3.13), Click CLI, typing |
| kaizen | Code quality discussions | Continuous improvement, poka-yoke, YAGNI, standardized work |
| software-architecture | Architecture decisions | Clean Architecture & DDD principles *(incomplete)* |

### git

Git workflows and GitHub integration.

| Skill | Triggers | Description |
|-------|----------|-------------|
| changelog-generator | "generate changelog", release prep | Transform commits into user-friendly changelogs |
| gh | GitHub CLI usage | PR management, GraphQL API, rate limits, Projects V2 |
| git-workflow-manager | Commits, releases | Conventional commits, semantic versioning, release workflow |

### web

Frontend development.

| Skill | Triggers | Description |
|-------|----------|-------------|
| vercel-react-best-practices | React/Next.js code | 45 performance rules from Vercel: waterfalls, bundles, SSR |
| web-artifacts-builder | "create artifact" | Build React artifacts for Claude.ai → single HTML bundle |
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
| linux-sysadmin | Linux admin tasks | Debian/Ubuntu: .d dirs, systemd, permissions, packages |

### meta

Claude Code tooling.

| Skill | Triggers | Description |
|-------|----------|-------------|
| cli-skill-creator | "create skill for CLI" | Meta-skill for creating CLI tool skills |
| mcp-builder | "build MCP server" | MCP server development: Python, Node.js, evaluations |
| claude-md-redirect | CLAUDE.md operations | Redirect to AGENTS.md with PostToolUse hook |
| claude-md-writer | "write CLAUDE.md" | CLAUDE.md best practices: size limits, 3-tier docs |
| opencode-config | OpenCode CLI setup | Custom providers, model selection, baseURL |
| statusline | — | Custom statusline showing costs & context usage |

### productivity

Analysis tools.

| Skill | Triggers | Description |
|-------|----------|-------------|
| meeting-insights-analyzer | "analyze meeting" | Communication patterns, speaking ratios, leadership style |

### agents

Custom agents for code tasks.

| Agent | Triggers | Description |
|-------|----------|-------------|
| python-code-reviewer | "review Python code" | READ-ONLY analysis, creates issue report with line numbers |
| python-quick-fixer | "fix Python issues" | Batch fixes from issue list: lint, types, code review comments |
| quick-worker | "do this task" | Fast executor for mechanical tasks: move files, restructure, batch edits |

## Requirements

- Claude Code CLI
- Git (for version control features)

## Project Structure

```
oh-my-claude-plugins/
├── agents/
├── coding-standards/
├── devops/
├── docs/
├── git/
├── meta/
├── productivity/
├── web/
└── marketplace.json
```

## Status Legend

| Marker | Meaning |
|--------|---------|
| *(incomplete)* | Needs work |
| *(guide)* | Reference only, no automation |

## License

Individual items may have their own licenses. Check each directory.
