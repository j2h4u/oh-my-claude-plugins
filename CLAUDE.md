@./AGENTS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**oh-my-claude-plugins** is a curated marketplace of Claude Code plugins organized into 8 plugin categories with 19 skills and 3 custom agents. Each plugin is self-contained with its own `plugin.json` manifest and follows Claude Code plugin development standards.

## Critical Constraints

**Skill description format (CRITICAL for discovery):**
- Must use third-person: "This skill should be used when..."
- Require 8-12 quoted trigger phrases users would say
- Anti-pattern: Imperative "Use when..." or no triggers
- See line 80-88 for exact format

**File size limits:**
- SKILL.md: 1,000-3,000 words (ideal)
- CLAUDE.md: < 200 lines (currently 158)
- references/ files: < 500 lines each

## Commands

### Validation

```bash
# Validate all plugin manifests (runs on CI)
jq empty .claude-plugin/marketplace.json
find . -name "plugin.json" -type f -exec jq empty {} \;

# Manual validation script (GitHub Actions workflow)
bash .github/workflows/validate-plugins.yml
```

### Version Management

```bash
# Bump marketplace version in .claude-plugin/marketplace.json
# Then tag and push:
git tag -a v1.x.x -m "Release v1.x.x — Description"
git push && git push --tags
```

### Testing Plugins Locally

```bash
# Add marketplace
/plugin marketplace add j2h4u/oh-my-claude-plugins

# Install specific plugin
/plugin install coding-standards@oh-my-claude-plugins
```

## Architecture

### Plugin Structure

Each plugin directory follows this pattern:

```
<category>/
├── plugin.json          # Plugin manifest with metadata
└── skills/              # Skills directory
    └── <skill-name>/
        ├── SKILL.md     # Main skill content (1,000-3,000 words)
        ├── references/  # Progressive disclosure (optional)
        └── examples/    # Working examples (optional)
```

### Marketplace Registry

- **`.claude-plugin/marketplace.json`** — Marketplace metadata, version, and plugin registry
- **`.claude-plugin/plugin.json`** — Aggregates all plugin.json files for marketplace discovery

### Quality System

Skills are rated ⭐⭐ to ⭐⭐⭐⭐⭐ based on:
1. **Structure** — Progressive disclosure, references/, examples/
2. **Completeness** — All sections present
3. **Depth** — Insights beyond surface level
4. **Originality** — Unique approach vs just packaging docs

See `SKILLS-REVIEW-REPORT.md` for detailed analysis and improvement roadmap.

## Development Standards

### Skill Description Format

```yaml
description: This skill should be used when the user asks to "trigger 1", "trigger 2", mentions "concept", or needs [use case].
```

### Bash Scripts

Follow **dignified-bash** (`coding-standards/skills/dignified-bash/`):
- `set -euo pipefail`
- `function die { ... } 1>&2`
- Function sections: `# args`, `# vars`, `# code`, `# result`
- Shellcheck compliant

### Git Workflow

Conventional commits → semantic versioning (`git-tools/skills/git-workflow-manager/`):
- `feat:` → MINOR, `fix:` → PATCH, `feat!:` → MAJOR

### Plugin Versioning (MANDATORY — never skip)

**ANY change to plugin files (even a single byte) MUST bump the patch version** in `<plugin>/.claude-plugin/plugin.json` and run `--sync`. No exceptions — cosmetic, refactor, one-liner, typo fix — all bump. This is the signal to marketplace clients that an update is available.

**Mandatory steps on EVERY commit that touches plugin files:**
1. Bump patch version in `<plugin>/.claude-plugin/plugin.json`
2. Run `./scripts/build-marketplace.py --sync` (auto-bumps marketplace version)
3. Commit both `plugin.json` and `marketplace.json` together

**Version sync:** After updating local `<plugin>/.claude-plugin/plugin.json`, run the build script:
```bash
./scripts/build-marketplace.py          # Show help (safe, no changes)
./scripts/build-marketplace.py --sync   # Sync versions to marketplace.json
./scripts/build-marketplace.py --check  # Validate only (for CI)
./scripts/build-marketplace.py --list   # Show all plugins with versions
```

## Key Patterns

### Plugin Categories

| Category | Purpose | Plugin Name |
|----------|---------|-------------|
| `coding-standards/` | Code quality, philosophy | coding-standards |
| `git-tools/` | Git workflows, GitHub | git-tools |
| `web-dev/` | Frontend development | web-frontend |
| `docs/` | Documentation creation | documentation |
| `devops/` | System administration | devops |
| `meta/` | Claude Code tooling | claude-code-meta |
| `productivity/` | Analysis tools | productivity |
| `agents/` | Custom agents | agents |

### Progressive Disclosure

Skills over 1,500 words should use references/:
- Core concepts in SKILL.md
- Detailed content in `references/<topic>.md`
- Examples in `examples/`
- Reference loading triggered by user patterns

### Marketplace Source Paths

The `source` field in marketplace.json must match directory names:
- `coding-standards/` → `"source": "./coding-standards"`
- `git/` → `"source": "./git"` (note: git-tools plugin uses `git/` directory)
- `web/` → `"source": "./web"` (note: web-frontend plugin uses `web/` directory)

## Documentation

- **README.md** — User-facing documentation with quality ratings
- **SKILLS-REVIEW-REPORT.md** — Comprehensive quality analysis and improvement roadmap
- **docs/plugin-development/** — Official Claude Code plugin development guides (schemas, best practices, templates)
- **docs/*.md** — Official Claude Code documentation (plugins.md, hooks.md, settings.md)

## CI/CD

GitHub Actions workflow validates:
- JSON syntax for all manifests
- Required fields in marketplace.json and plugin.json files
- No duplicate plugin names
- YAML frontmatter in command files
- Plugin directory structure

Runs on push to `main`/`develop` and all pull requests.
