# OMCC Statusline — Slot-based multi-line statusline with git, PR dots, and token tracking

Enhanced statusline for Claude Code with a **slot system** — each line is a slot that can be a built-in provider or an external command. Supports N lines, backward compatible.

## Preview

**3-line with GSD slot (external command):**
```
🤖 Opus 4.6 | 💰 $25.17 session              ← ccusage (built-in)
⬆ /gsd:update │ Fixing auth bug │ █████░░░░░ 52%  ← gsd (external command)
my-project/ ⑂main*+ CI | ⁕⁕💬2                ← git (built-in)
```

**Default 2-line (no slots config):**
```
🤖 Sonnet 4.5 | 💰 $12.34 session
my-project/ ⑂feat/auth*+ CI | ⁕⁕⁕💬3
```

**When `gh` not installed:**
```
🤖 Sonnet 4.5 | 💰 $0.42 session
my-project/ ⑂main | gh not installed
```

**Format:**
```
Line N: each slot renders one line (empty slots are skipped)
```

### Slot System

Each slot is either a **built-in provider** or an **external command**. Slots run in parallel for speed.

**Built-in providers:**
- `git` — Directory + branch + git status + CI + PR dots + notifications

**External commands:** Any shell command that reads JSON from stdin and outputs one line to stdout. Executed as fire-and-forget background subprocesses with flock — never blocks the statusline. Default setup includes `ccusage` as a command slot.

### Git Line Elements

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

4. (Optional) Configure slots in `~/.config/omcc-statusline/theme.json`:

```json
{
  "slots": [
    {"command": "bun x ccusage statusline --visual-burn-rate text --refresh-interval 60", "ttl": 300},
    {"command": "node ~/.claude/hooks/gsd-statusline.js"},
    {"provider": "git"}
  ],
  "dir_parent": {"fg": 239}
}
```

Each slot: `{"command": "<shell cmd>"}` for external commands, or `{"provider": "git"}` for the built-in git line.
Optional `"ttl": <seconds>` controls cache lifetime (default: 60s). Commands run as background subprocesses with flock.

**No `slots` key** = default `[ccusage (command, ttl=300), git (provider)]`.

5. Restart Claude Code.

### Test the statusline

```bash
# Run demo (shows all scenarios)
python3 omcc-statusline.py --demo

# Test with real data
echo '{"workspace":{"current_dir":"'"$(pwd)"'"}}' | python3 omcc-statusline.py
```

## How It Works

1. **Reads JSON from Claude Code stdin** — Contains workspace directory, model, tokens, costs
2. **Loads slot config** from `~/.config/omcc-statusline/theme.json` (or defaults to `[ccusage, git]`)
3. **Executes all slots in parallel** via thread pool — built-in providers and external commands run concurrently
4. **Each slot produces one line** — empty lines are filtered out
5. **Returns styled multi-line output** — ANSI colors based on theme config

### Slot Execution

All slots run concurrently in a thread pool. Built-in providers (`ccusage`, `git`) handle their own data fetching internally. External commands receive the full JSON on stdin and must output one line to stdout.

**External command caching:** Output is cached in `/tmp/omcc-statusline/slots/` with configurable TTL (default 60s). On failure/timeout (5s limit), stale cache is used as fallback.

### PR Status Caching

PR data is cached to avoid blocking statusline render:

- **Cache location:** `~/.config/omcc-statusline/` (config) + `/tmp/omcc-statusline/` (runtime cache)
- **Theme config:** `~/.config/omcc-statusline/theme.json`
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
- Check cache: `cat /tmp/omcc-statusline/pr-status.json | jq .prs.data.search.nodes`
- Force refresh: `rm -rf /tmp/omcc-statusline/`

**Theme not applying:**
- Restart Claude Code after saving theme
- Verify config exists: `cat ~/.config/omcc-statusline/theme.json`

**Performance issues:**
- PR/CI fetches happen in background, shouldn't block statusline
- First run may take up to 5s (all caches miss) — subsequent renders use cache
- If statusline is slow, it's usually ccusage itself, not this script
