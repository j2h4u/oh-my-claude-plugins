---
name: metabase
description: This skill should be used when the user asks to "check metabase status", "inspect metabase", "find duplicate cards", "diagnose metabase issues", "backup metabase", "restore metabase backup", "create metabase card", "create metabase dashboard", "add card to dashboard", "run metabase query", mentions "metabase dashboards", "metabase cards", or needs to manage Metabase content via CLI.
---

# Metabase CLI

CLI: `scripts/metabase-cli.py`

> **Note:** All script paths are relative to the skill directory (`scripts/` folder inside the skill root).

## Quick Start

```bash
# Overview with tree view
python scripts/metabase-cli.py inspect

# Diagnostics (duplicates, empty cards, integrity)
python scripts/metabase-cli.py diag

# Backup everything
python scripts/metabase-cli.py backup -f backup.zip
```

## Commands

### System
```bash
inspect                          # Show version, stats, dashboards tree
diag                             # Duplicates, empty cards, broken links
backup [-f FILE]                 # Backup cards+dashboards to ZIP
restore -f FILE [--db ID]        # Restore from ZIP
```

### Cards
```bash
card list                        # List all cards
card get <id>                    # Get card details with SQL
card create --name N --sql S     # Create SQL card (--display line|bar|pie|table)
card update <id> [--sql] [--name]
card delete <id>
```

### Dashboards
```bash
dashboard list
dashboard get <id>               # Shows cards with positions
dashboard create --name N
dashboard add-card <dash> <card> [--row R --col C --size-x W --size-y H]
dashboard delete <id>
```

### Query
```bash
query "SELECT * FROM tracks LIMIT 5"
```

## Options

`--json` — Machine-readable JSON output (no colors, no UI messages)

## Exit Codes

- `0` — Success, no issues found
- `1` — Issues found (duplicates, broken links, etc.) or error occurred

```bash
python scripts/metabase-cli.py --json card list
python scripts/metabase-cli.py --json inspect
```

## Display Types

`table`, `bar`, `line`, `pie`, `area`, `scalar`, `row`, `funnel`, `progress`, `gauge`

## Key Tables

| Table | Content |
|-------|---------|
| `agg_by_track` | Revenue/royalty per track |
| `agg_by_licensee` | Revenue/royalty per licensee |
| `agg_by_platform` | Revenue/royalty per platform |
| `agg_by_artist` | Revenue/royalty per artist |
| `agg_by_territory` | Revenue/royalty per territory |

Columns: `period_code`, `total_net`, `total_royalty`, `cp_royalty`, `stream_count`

## Workflow: New Dashboard

```bash
# 1. Create cards
python scripts/metabase-cli.py card create \
  --name "Total Revenue" \
  --sql "SELECT SUM(total_net) FROM agg_by_licensee" \
  --display scalar
# → {"id": 170, ...}

python scripts/metabase-cli.py card create \
  --name "Revenue Trend" \
  --sql "SELECT period_code, SUM(total_net) FROM agg_by_track GROUP BY 1 ORDER BY 1" \
  --display line
# → {"id": 171, ...}

# 2. Create dashboard
python scripts/metabase-cli.py dashboard create --name "Overview"
# → {"id": 8, ...}

# 3. Add cards (grid is 24 cols wide)
python scripts/metabase-cli.py dashboard add-card 8 170 --row 0 --col 0 --size-x 6 --size-y 4
python scripts/metabase-cli.py dashboard add-card 8 171 --row 0 --col 6 --size-x 18 --size-y 8
```

## Advanced

See `reference.md` for API nuances: dependency resolution, bulk updates, negative IDs.
