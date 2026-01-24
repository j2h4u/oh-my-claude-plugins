# Metabase CLI

> Swiss Army Knife for Metabase.

**Find duplicate cards, backup dashboards, and manage Metabase — all from the terminal.**

One Python script, zero dependencies. Works with any Metabase instance.

## What It Does

- **Diagnose problems** — Find duplicate card names, empty cards, broken links. Get IDs for cleanup.
- **Backup & restore** — Export everything to ZIP. Migrate between instances.
- **Manage content** — Create, update, delete cards and dashboards without the UI.
- **Run queries** — Execute SQL directly from the command line.

## Quick Start

```bash
# 1. Set credentials
export METABASE_URL=http://localhost:3000
export METABASE_ADMIN_EMAIL=admin@example.com
export METABASE_ADMIN_PASSWORD=secret

# 2. Check what you have
./metabase-cli.py inspect

# 3. Find problems
./metabase-cli.py diag
```

## Requirements

- Python 3.10+
- Metabase with admin credentials

## Usage

### Find Problems

```bash
./metabase-cli.py diag
```

Output:
```
→ Running Metabase diagnostics...
⚠ Found 3 duplicate card names:
   'Revenue Chart': IDs [42, 87]
   'Monthly Stats': IDs [15, 23, 91]
✓ Dashboard 'Overview': 5 cards OK
⚠ Diagnostics complete: 3 issues found.
```

### Backup Everything

```bash
./metabase-cli.py backup -f backup.zip
```

Creates a ZIP with all cards and dashboards. Safe to restore on another instance.

### Create a Dashboard

```bash
# Create cards
./metabase-cli.py card create --name "Total Sales" \
  --sql "SELECT SUM(amount) FROM orders" --display scalar

./metabase-cli.py card create --name "Sales Trend" \
  --sql "SELECT date, SUM(amount) FROM orders GROUP BY date" --display line

# Create dashboard and add cards
./metabase-cli.py dashboard create --name "Sales"
./metabase-cli.py dashboard add-card 1 1 --size-x 6 --size-y 4
./metabase-cli.py dashboard add-card 1 2 --col 6 --size-x 18 --size-y 8
```

## Commands

| Command | What it does |
|---------|--------------|
| `inspect` | Show version, stats, dashboard tree |
| `diag` | Find duplicates, empty cards, broken links |
| `backup -f FILE` | Export all content to ZIP |
| `restore -f FILE` | Import from ZIP (idempotent) |
| `card list/get/create/update/delete` | Manage cards |
| `dashboard list/get/create/delete` | Manage dashboards |
| `dashboard add-card` | Add card to dashboard |
| `query "SQL"` | Run ad-hoc query |

## Options

| Option | Description |
|--------|-------------|
| `--json` | Machine-readable output |
| `--display TYPE` | Card type: `table`, `bar`, `line`, `pie`, `scalar` |
| `--db ID` | Target database for restore |

## Configuration

Create `.env` in current directory:

```
METABASE_URL=http://localhost:3000
METABASE_ADMIN_EMAIL=admin@example.com
METABASE_ADMIN_PASSWORD=secret
```

Or export environment variables directly.

## Agent Skills Integration

This script is designed to work as an [Agent Skill](https://docs.anthropic.com/en/docs/claude-code/skills) for Claude Code and similar AI coding assistants.

**Why it works well as a skill:**

- **JSON mode** — `--json` flag outputs structured data that agents can parse and act on
- **Atomic commands** — Each command does one thing, easy to chain
- **Self-documenting** — `--help` and error messages guide the agent
- **Zero setup** — No dependencies, just point to the script

**Example skill structure:**

```
skills/metabase/
├── SKILL.md          # Instructions for the agent
├── reference.md      # API nuances and edge cases
└── scripts/
    └── metabase-cli.py
```

The `SKILL.md` tells the agent when to use the tool and adds project-specific context (table schemas, common queries, workflows).

**In this project**, the skill triggers on "dashboard", "metabase", "visualization" and provides Copper Pipes database schema context.

## License

[Polyform Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — Free for personal and educational use. Commercial use requires permission.

---

*Best practices from [Make a README](https://www.makeareadme.com/) and [PyOpenSci Guide](https://www.pyopensci.org/python-package-guide/documentation/repository-files/readme-file-best-practices.html).*
