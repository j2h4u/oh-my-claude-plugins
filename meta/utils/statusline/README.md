# OMCC Statusline — Two-line statusline with git, PR dots, and token tracking

Enhanced statusline for Claude Code: directory + git status + PR indicators on line 2, ccusage metrics on line 1.

## Preview

```
🤖 Sonnet 4.5 | 💰 $25.17 session
j2h4u/ ⑂main*+ CI | ⁕⁕💬2
```

**Mixed PR states (red/blue/green/gray dots):**
```
🤖 Opus 4.6 | 💰 $58.07 session
my-project/ ⑂feat/auth*+ CI | ⁕⁕⁕💬3
```

**When `gh` not installed:**
```
🤖 Sonnet 4.5 | 💰 $0.42 session
my-project/ ⑂main | gh not installed
```

**Format:**
```
Line 1: <ccusage metrics>
Line 2: <dir>/ ⑂<branch><git_indicators> [CI] [PR_dots] [💬N]
```

### Elements

- **Line 1:** Model name, costs, token burn rate (from `ccusage`)
- **dir/** — Current directory (muted gray)
- **⑂main** — Git branch indicator + branch name (dimmed)
- **\* + ? ↑ ↓** — Git status:
  - `*` dirty (unstaged changes, yellow dim)
  - `+` staged changes (green dim)
  - `?` untracked files (gray)
  - `↑` ahead of remote (cyan)
  - `↓` behind remote (purple)
- **CI** — Current branch CI status (color conveys result: 🟢 green | 🔴 red | 🔵 blue)
- **⁕⁕⁕** — PR dots (one dot per open PR, color = CI state: red | blue | green | gray)
- **💬3** — Unread notifications from participating PRs/issues (cyan, only shown when > 0)

## Requirements

- **Python 3.10+** — Runtime for statusline renderer
- **`bun`** — For running ccusage
- [`ccusage`](https://github.com/ryoppippi/ccusage) — Claude Code usage tracker (runs via `bun x`)
- **`gh`** (optional) — GitHub CLI for PR indicators. If missing, shows error in red.

### Install dependencies

```bash
# macOS
brew install bun

# Debian/Ubuntu
curl -fsSL https://bun.sh/install | bash

# ccusage runs via bunx, no install needed
# gh (optional)
brew install gh   # or: apt install gh
```

## Installation

1. The script deploys via marketplace to: `~/.claude/plugins/marketplace/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py`

2. Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/plugins/marketplace/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py"
  }
}
```

3. (Optional) Customize theme by running the editor:

```bash
python3 ~/.claude/plugins/marketplace/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py --theme
```

4. Restart Claude Code.

### Test the statusline

```bash
# Run demo (shows all scenarios)
python3 omcc-statusline.py --demo

# Test with real data
echo '{"workspace":{"current_dir":"'"$(pwd)"'"}}' | python3 omcc-statusline.py
```

## How It Works

1. **Reads JSON from Claude Code stdin** — Contains workspace directory, model, tokens, costs
2. **Extracts directory name** — Current dir + parent dir (truncated)
3. **Fetches git info** — Branch name, ahead/behind counts, working tree status
4. **Fetches PR status** (background, cached) — Open PRs via GitHub GraphQL API
5. **Fetches CI status** (cached) — Per-branch check-runs via GitHub REST API
6. **Fetches ccusage** — Token usage, burn rate, costs (via `bun x ccusage`)
7. **Formats two-line output** — Parallel thread pool for fast concurrent fetches
8. **Returns styled output** — ANSI colors based on theme config

### Parallel Fetching

Four independent data sources fetch concurrently in thread pool:
- Git info (subprocess, ~100ms)
- PR status (disk cache read, ~5ms on cache hit)
- ccusage (subprocess, variable)
- CI status (depends on git branch, runs after git completes)

Blocking on any one source doesn't delay the others.

### PR Status Caching

PR data is cached to avoid blocking statusline render:

- **Cache location:** `~/.config/claude-statusline/` (config) + `/tmp/claude-statusline/` (runtime cache)
- **Theme config:** `~/.config/claude-statusline/theme.json`
- **PR cache TTL:** 5 minutes
- **CI cache TTL:** 2 minutes
- **GH availability check TTL:** 30 minutes
- **Background refresh:** When cache is stale, a detached subprocess fetches new data
- **Lock file:** File-level lock prevents parallel refresh processes
- **Atomic writes:** Temp file + `os.replace()` ensures no partial cache reads

### Theme Editor

Interactive TUI for customizing colors and text attributes:

```bash
python3 ~/.claude/plugins/marketplace/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py --theme
```

**In editor:**
- **← →** Navigate elements (dir, branch, git status, CI, PR, notifications, etc.)
- **f** Pick foreground color (256-color palette with live preview)
- **b** Pick background color
- **a** Toggle text attributes (dim, bold, italic, underline, etc.)
- **c** Copy current element style
- **v** Paste to current element
- **s** Save config to `~/.config/claude-statusline/theme.json`
- **r** Reset current element to default
- **R** Reset all elements to defaults
- **q** Quit

**Colors:** Full 256-color ANSI palette + attributes (dim, bold, italic, underline variants, blink, strike, reverse, overline).

**Defaults:** All elements already have sensible defaults. Edit theme only if you want custom colors.

## Troubleshooting

**Statusline not showing:**
- Check `~/.claude/settings.json` syntax (use absolute path)
- Verify script is executable: `chmod +x omcc-statusline.py`
- Check Python version: `python3 --version` (needs 3.10+)
- Test manually: `python3 omcc-statusline.py --demo`

**Statusline shows error messages in red:**
- `bun not found` — Install bun: https://bun.sh/
- `ccusage error` — Ensure bun can run ccusage: `bun x ccusage --help`
- `gh not installed` — Install gh (optional): https://cli.github.com/
- `gh auth login` — Authenticate: `gh auth login`

**Git branch not showing:**
- Only displays when in a git repository
- Check: `git branch --show-current`

**PR dots not showing:**
- Requires `gh` CLI installed and authenticated
- First render may show nothing (refreshes in background)
- Subsequent renders show cached PR data
- Check cache: `cat /tmp/claude-statusline/pr-status.json | jq .prs.data.search.nodes`
- Force refresh: `rm -rf /tmp/claude-statusline/`

**Theme not applying:**
- Restart Claude Code after saving theme
- Verify config exists: `cat ~/.config/claude-statusline/theme.json`

**Performance issues:**
- PR/CI fetches happen in background, shouldn't block statusline
- First run may take up to 5s (all caches miss) — subsequent renders use cache
- If statusline is slow, it's usually ccusage itself, not this script
