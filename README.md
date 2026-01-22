# Oh My Claude Plugins

**Curated collection of Claude Code plugins for everyday development.**

Skills, agents, and hooks that make Claude Code smarter about your workflow — from coding standards to git automation.

[![GitHub stars](https://img.shields.io/github/stars/j2h4u/oh-my-claude-plugins?style=social)](https://github.com/j2h4u/oh-my-claude-plugins/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Validate Plugins](https://github.com/j2h4u/oh-my-claude-plugins/actions/workflows/validate-plugins.yml/badge.svg)](https://github.com/j2h4u/oh-my-claude-plugins/actions/workflows/validate-plugins.yml)

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

| Skill | Triggers | Description | Quality | Notes |
|-------|----------|-------------|---------|-------|
| dignified-bash | Writing bash scripts | Strict mode, shellcheck, defensive patterns | ⭐⭐⭐⭐ | Well-structured but standard bash practices |
| dignified-python | Writing Python code | LBYL philosophy, version-aware (3.10-3.13), Click CLI | ⭐⭐⭐⭐⭐ | Deep LBYL approach, original error-handling philosophy |
| kaizen | Code quality discussions | Continuous improvement, poka-yoke, YAGNI | ⭐⭐⭐⭐⭐ | Deep principles with original code adaptation |
| software-architecture | Architecture decisions | Clean Architecture & DDD principles | ⭐⭐ | Needs examples, library guide |

### git-tools

Git workflows and GitHub integration.

| Skill | Triggers | Description | Quality | Notes |
|-------|----------|-------------|---------|-------|
| changelog-generator | "generate changelog" | Transform commits into user-friendly changelogs | ⭐⭐⭐ | Shallow workflow, not deep |
| gh | GitHub CLI usage | PR management, GraphQL API, Projects V2 | ⭐⭐⭐⭐⭐ | Deep mental model, original workflow patterns |
| git-workflow-manager | Commits, releases | Conventional commits, semantic versioning | ⭐⭐⭐ | Basic conventional commits reference |

### web-dev

Frontend development.

| Skill | Triggers | Description | Quality | Notes |
|-------|----------|-------------|---------|-------|
| vercel-react-best-practices | React/Next.js code | 45 performance rules: waterfalls, bundles, SSR | ⭐⭐⭐⭐ | Great structure but just packages Vercel rules |
| web-artifacts-builder | "create artifact" | Build React artifacts for Claude.ai | ⭐⭐ | Needs troubleshooting guide, component patterns, examples |
| web-design-guidelines | UI review | Vercel Web Interface Guidelines | ⭐⭐ | Needs expansion (176→1500 words), sample output examples |

### docs

Documentation creation.

| Skill | Triggers | Description | Quality | Notes |
|-------|----------|-------------|---------|-------|
| doc-coauthoring | "help write doc" | Collaborative workflow: gathering, refinement, reader testing | ⭐⭐⭐⭐ | Good workflow but not particularly deep |
| readme-generator | "write README" | README best practices by project type | ⭐⭐⭐ | Just a process, shallow content |

### devops

System administration.

| Skill | Triggers | Description | Quality | Notes |
|-------|----------|-------------|---------|-------|
| linux-sysadmin | Linux admin tasks | Debian/Ubuntu: systemd, permissions, packages | ⭐⭐⭐⭐ | Useful practices, standard content |

### claude-code-meta

Claude Code tooling and meta-skills.

| Skill | Triggers | Description | Quality | Notes |
|-------|----------|-------------|---------|-------|
| cli-skill-creator | "create skill for CLI" | Meta-skill for creating CLI tool skills | ⭐⭐⭐⭐⭐ | Deep systematic approach, highly original meta-skill |
| mcp-builder | "build MCP server" | MCP server development: Python, Node.js | ⭐⭐⭐⭐⭐ | Deep best practices, includes working evaluation tools |
| claude-md-redirect | CLAUDE.md operations | Redirect to AGENTS.md with PostToolUse hook | ⭐⭐⭐ | Utility skill, very shallow |
| claude-md-writer | "write CLAUDE.md" | CLAUDE.md best practices: size limits, 3-tier docs | ⭐⭐⭐⭐ | Good compilation of best practices |
| opencode-config | OpenCode CLI setup | Custom providers, model selection | ⭐⭐⭐ | Just config reference, shallow |

**Utility:** `statusline` — Custom statusline showing costs & context usage. Install via `@"statusline-setup"` agent.

### productivity

Analysis tools.

| Skill | Triggers | Description | Quality | Notes |
|-------|----------|-------------|---------|-------|
| meeting-insights-analyzer | "analyze meeting" | Communication patterns, speaking ratios | ⭐⭐⭐⭐ | Original approach to meeting analysis |

### agents

Custom agents for code tasks.

| Agent | Triggers | Description |
|-------|----------|-------------|
| python-code-reviewer | "review Python code" | READ-ONLY analysis, creates issue report |
| python-quick-fixer | "fix Python issues" | Batch fixes from issue list |
| quick-worker | "do this task" | Fast executor for mechanical tasks |

---

## Skills by Quality

Quick overview grouped by rating to identify improvement priorities:

### ⭐⭐⭐⭐⭐ Exemplary (5 skills)

Deep insights + original approaches, comprehensive content:

| Skill | Category | What makes it exemplary |
|-------|----------|-------------------------|
| **gh** | git-tools | Deep mental model, original workflow patterns, exemplary progressive disclosure |
| **mcp-builder** | claude-code-meta | Deep best practices, includes working evaluation tools |
| **cli-skill-creator** | claude-code-meta | Highly original meta-skill, systematic CLI introspection approach |
| **dignified-python** | coding-standards | Deep LBYL philosophy, original error-handling approach |
| **kaizen** | coding-standards | Deep principles with original adaptation to code |

### ⭐⭐⭐⭐ High Quality (7 skills)

Good depth, well-structured, production ready:

| Skill | Category | Notes |
|-------|----------|-------|
| **dignified-bash** | coding-standards | Well-structured but standard bash practices |
| **linux-sysadmin** | devops | Useful practices, standard content |
| **doc-coauthoring** | docs | Good workflow but not particularly deep |
| **claude-md-writer** | claude-code-meta | Good compilation of best practices |
| **meeting-insights-analyzer** | productivity | Original approach to meeting analysis |
| **vercel-react-best-practices** | web-dev | Great structure but just packages Vercel rules |

### ⭐⭐⭐ Solid but Shallow (5 skills)

**⚠️ Candidates for replacement/deepening** — Complete but lacking depth or originality:

| Skill | Category | Why shallow/standard | Replacement strategy |
|-------|----------|----------------------|----------------------|
| **changelog-generator** | git-tools | Just a workflow, not deep | Find deeper changelog philosophy/patterns |
| **git-workflow-manager** | git-tools | Basic conventional commits reference | Find advanced git workflow patterns |
| **opencode-config** | claude-code-meta | Just config reference, shallow | Find deeper OpenCode configuration insights |
| **claude-md-redirect** | claude-code-meta | Utility, very shallow | Consider removing or expanding |
| **readme-generator** | docs | Just process, shallow content | Find README philosophy/patterns beyond basics |

### ⭐⭐ Incomplete (3 skills)

**🚨 Priority for improvement** — Functional but missing critical content:

| Skill | Category | What's missing | Search for |
|-------|----------|----------------|------------|
| **software-architecture** | coding-standards | Needs examples, library guide | Code pattern examples, library-first guides |
| **web-artifacts-builder** | web-dev | Needs troubleshooting guide, component patterns, examples | React artifact patterns, debugging guides |
| **web-design-guidelines** | web-dev | Needs expansion (176→1500 words), sample output examples | UI/UX guidelines, review examples |

---

### Quality Rating

Quality is rated on **four dimensions**:

1. **Structure** — Progressive disclosure, references/, examples/, clear organization
2. **Completeness** — All sections present, no missing content
3. **Depth** — Insights beyond surface level, practical patterns, deep understanding
4. **Originality** — Unique approach or just packaging existing docs/tools

| Stars | Meaning | Examples |
|-------|---------|----------|
| ⭐⭐⭐⭐⭐ | Exemplary — deep + original + comprehensive | gh (mental model), mcp-builder (evaluation tools), kaizen (code adaptation) |
| ⭐⭐⭐⭐ | High quality — good depth + well-structured | dignified-bash, linux-sysadmin, meeting-insights-analyzer |
| ⭐⭐⭐ | Solid — complete but shallow/standard | changelog-generator (just workflow), opencode-config (config reference) |
| ⭐⭐ | Incomplete — needs expansion or examples | software-architecture, web-artifacts-builder, web-design-guidelines |

**Why downgraded from 5→3 stars?**
- Just a workflow without deep insights (changelog-generator)
- Simple reference/config guide (git-workflow-manager, opencode-config)
- Packaging existing docs without original approach (vercel-react-best-practices)
- Utility skill without depth (claude-md-redirect)

Check **Notes** column for specifics. See [SKILLS-REVIEW-REPORT.md](SKILLS-REVIEW-REPORT.md) for detailed improvement roadmap.

## Alternative Installation

Use as local plugin directory (development mode):

```bash
claude --plugin-dir /path/to/oh-my-claude-plugins
```

## Documentation

### Plugin System Guides (`docs/`)

Comprehensive documentation for Claude Code plugin development:

| Guide | Description |
|-------|-------------|
| [Plugins](docs/plugins.md) | Plugin development quickstart |
| [Plugins Reference](docs/plugins-reference.md) | Technical specifications and schemas |
| [Plugin Marketplaces](docs/plugin-marketplaces.md) | Marketplace creation and management |
| [Hooks](docs/hooks.md) | Event-driven automation (27KB reference) |
| [Skills](docs/skills.md) | Agent skills development |
| [Sub-Agents](docs/sub-agents.md) | Specialized AI assistants |
| [Slash Commands](docs/slash-commands.md) | Command system reference |
| [Settings](docs/settings.md) | Configuration guide (46KB) |

### Plugin Development Resources (`docs/plugin-development/`)

Advanced guides for plugin developers:

| Resource | Description |
|----------|-------------|
| [Schemas](docs/plugin-development/schemas/) | Complete schemas for plugin.json, hooks, marketplace (1,479 lines) |
| [Best Practices](docs/plugin-development/best-practices/) | Organization, naming conventions, common mistakes (1,156 lines) |
| [Templates](docs/plugin-development/templates/) | Ready-to-use templates for all plugin components |
| [Examples](docs/plugin-development/examples/) | Complete plugin walkthrough and testing workflow |

### Skill Quality & Improvement Roadmap

Quality indicators are shown in the skill tables above. For detailed analysis including:
- Specific issues and recommended fixes
- Missing content (examples, troubleshooting guides)
- Word count analysis and expansion needs
- Priority-ordered improvement roadmap

See [SKILLS-REVIEW-REPORT.md](SKILLS-REVIEW-REPORT.md) — comprehensive review of all 19 skills with actionable improvement suggestions.

## Requirements

- Claude Code CLI
- Git (for version control features)

## Contributing

Plugin validation runs automatically on every push via GitHub Actions. To validate locally:

```bash
# Check JSON syntax
jq empty .claude-plugin/marketplace.json

# Validate plugin structure
bash .github/workflows/validate-plugins.yml
```

## Acknowledgments

Inspired by [Claude Code Plugin Template](https://github.com/ivan-magda/claude-code-plugin-template) by Ivan Magda. Plugin development documentation (schemas, best practices, templates) adapted from the template's plugin-authoring skill.

## License

Individual items may have their own licenses. Check each directory.
