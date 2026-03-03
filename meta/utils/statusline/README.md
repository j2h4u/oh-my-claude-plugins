# OMCC Statusline — Slot-based multi-line statusline with limits, git, and PR dots

Enhanced statusline for Claude Code with a **slot system** — each line is a slot that can be a built-in provider or an external command. Supports N lines, backward compatible.

## Preview

**Default 2-line (limits + git):**
```
5h ▋     12% · 7d █▊    35% · vibing ↓11% · ctx 24%
my-project/ ⑂feat/auth*+ CI · ⁕⁕⁕💬3
```

**5h exhausted (red), 7d for context:**
```
5h █████ 100% 23m · 7d ████  80% 1d 5h · vibing ↓20% · ctx 80%
my-project/ ⑂main*+ CI · ⁕⁕
```

**7d exhausted — only 7d shown:**
```
7d █████ 100% 2d 4h · ok ↑3% · ctx 45%
my-project/ ⑂develop ↑
```

**3-line with GSD slot (external command):**
```
5h ▏     5% · 7d ▉     18% · vibing ↓28% · ctx 30%
⬆ /gsd:update │ Fixing auth bug │ █████░░░░░ 52%
my-project/ ⑂main*+ CI · ⁕⁕💬2
```

**Format:**
```
Line N: each slot renders one line (empty slots are skipped)
```

### Slot System

Each slot is either a **built-in provider** or an **external command**. Slots run in parallel for speed.

**Built-in providers:**
- `limits` — API usage limits (5h/7d windows with bar, percentage, pace, reset countdown) + context window utilization
- `git` — Directory + branch + git status + CI + PR dots + notifications

**External commands:** Any shell command that reads JSON from stdin and outputs one line to stdout. Executed as fire-and-forget background subprocesses with flock — never blocks the statusline.

### Limits Line Elements

```
5h ▋     12% · 7d █▊    35% · vibing ↓11% · ctx 24%
```

- **`5h` / `7d`** — Window label (5-hour and 7-day rolling usage windows)
- **`▋    `** — Progress bar (5 chars, Unicode block precision, dark gray background, color adaptive: green < 50% / orange 50–80% / red > 80%)
- **`12%`** — Utilization percentage
- **`4h26m`** — Reset countdown (only shown when utilization ≥ 50%)
- **`·`** — Separator between sections
- **`vibing ↓11%`** — Pace indicator (7d window only, see below)
- **`ctx 24%`** — Context window utilization

**Hierarchical display logic:**
- Normal: both `5h` and `7d` shown
- `5h ≥ 100%`: both shown (5h in red, 7d for context)
- `7d ≥ 100%`: only `7d` shown (focus on weekly limit)

### Pace Indicator

Compares actual 7d utilization against expected pace assuming a **5-day × 24h = 120h working budget**.

| Label | Meaning | Delta |
|-------|---------|-------|
| `vibing` 🟢 | Well under budget | ≤ −10 pp |
| `ok` ⬜ | On track | ≤ +10 pp |
| `easy` 🟡 | Slightly over | ≤ +25 pp |
| `brake` 🔴 | Significantly over | > +25 pp |

The **`↑` / `↓`** suffix shows how many percentage points above/below expected pace:
- `vibing ↓11%` — 11% below expected pace (good)
- `brake ↑35%` — 35% above expected pace (slow down)

Pace is hidden at session start when not enough time has elapsed to compute a meaningful expected value.

### Git Line Elements

- **dir/** — Current directory (muted gray)
- **⑂main** — Git branch indicator + branch name (dimmed)
- **`* + ? ↑ ↓`** — Git status:
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
- **Claude Code OAuth** — Limits provider reads token from `~/.claude/.credentials.json` (auto-created by Claude Code)
- **`gh`** (optional) — GitHub CLI for PR indicators. If missing, shows error in red.

### Install dependencies

```bash
# gh (optional)
brew install gh   # or: apt install gh
```

## Installation

1. The script deploys via marketplace to: `~/.claude/plugins/marketplaces/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py`

2. Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/plugins/marketplaces/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py"
  }
}
```

3. (Optional) Customize theme by running the editor:

```bash
python3 ~/.claude/plugins/marketplaces/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py --theme
```

4. (Optional) Configure slots in `~/.config/omcc-statusline/config.json`:

```json
{
  "slots": [
    {"provider": "limits"},
    {"command": "node ~/.claude/hooks/gsd-statusline.js"},
    {"provider": "git"}
  ],
  "dir_parent": {"fg": 239}
}
```

Each slot: `{"command": "<shell cmd>"}` for external commands, or `{"provider": "limits"}` / `{"provider": "git"}` for built-in providers.
Optional `"ttl": <seconds>` controls cache lifetime for commands (default: 60s). Commands run as background subprocesses with flock.
Optional `"enabled": false` disables a slot without removing it from config (default: `true`).

**No `slots` key** = default `[limits (provider), git (provider)]`.

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
2. **Loads slot config** from `~/.config/omcc-statusline/config.json` (or defaults to `[limits, git]`)
3. **Executes all slots in parallel** via thread pool — built-in providers and external commands run concurrently
4. **Each slot produces one line** — empty lines are filtered out
5. **Returns styled multi-line output** — ANSI colors based on theme config

### Slot Execution

All slots run concurrently in a thread pool. Built-in providers (`limits`, `git`) handle their own data fetching internally. External commands receive the full JSON on stdin and must output one line to stdout.

**External command caching:** Output is cached in `/tmp/omcc-statusline/slots/` with configurable TTL (default 60s). On failure/timeout (5s limit), stale cache is used as fallback.

### PR Status Caching

PR data is cached to avoid blocking statusline render:

- **Cache location:** `~/.config/omcc-statusline/` (config) + `/tmp/omcc-statusline/` (runtime cache)
- **Theme config:** `~/.config/omcc-statusline/config.json`
- **Limits cache TTL:** 2 minutes
- **PR cache TTL:** 5 minutes
- **CI cache TTL:** 2 minutes
- **GH availability check TTL:** 30 minutes
- **Background refresh:** When cache is stale, a detached subprocess fetches new data
- **Lock file:** File-level lock prevents parallel refresh processes
- **Atomic writes:** Temp file + `os.replace()` ensures no partial cache reads

### Theme Editor

Interactive TUI for customizing colors and text attributes:

```bash
python3 ~/.claude/plugins/marketplaces/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py --theme
```

**In editor:**
- **← →** Navigate elements (dir, branch, git status, CI, PR, notifications, etc.)
- **f** Pick foreground color (256-color palette with live preview)
- **b** Pick background color
- **a** Toggle text attributes (dim, bold, italic, underline, etc.)
- **c** Copy current element style
- **v** Paste to current element
- **s** Save config to `~/.config/omcc-statusline/config.json`
- **r** Reset current element to default
- **R** Reset all elements to defaults
- **q** Quit

**Colors:** Full 256-color ANSI palette + attributes (dim, bold, italic, underline variants, blink, strike, reverse, overline).

**Defaults:** All elements already have sensible defaults. Edit theme only if you want custom colors.

## Troubleshooting

**Statusline not showing:**
- Check `~/.claude/settings.json` syntax (use absolute path)
- Check Python version: `python3 --version` (needs 3.10+)
- Test manually: `echo '{}' | python3 omcc-statusline.py --demo`

**Statusline shows error messages in red:**
- `gh not installed` — Install gh (optional): https://cli.github.com/
- `gh auth login` — Authenticate: `gh auth login`

**Limits line not showing:**
- First render is always empty (background fetch in progress) — appears on second render
- Check credentials: `cat ~/.claude/.credentials.json | python3 -c "import json,sys; print(json.load(sys.stdin)['claudeAiOauth']['accessToken'][:20]+'...')"`
- Test API manually: `python3 -c "from urllib.request import Request, urlopen; import json; from pathlib import Path; t=json.loads(Path.home().joinpath('.claude/.credentials.json').read_text())['claudeAiOauth']['accessToken']; r=Request('https://api.anthropic.com/api/oauth/usage'); r.add_header('Authorization',f'Bearer {t}'); r.add_header('anthropic-beta','oauth-2025-04-20'); print(json.dumps(json.loads(urlopen(r,timeout=5).read()),indent=2))"`
- Force refresh: `rm /tmp/omcc-statusline/limits-cache.json`

**Pace not showing:**
- Hidden until enough time has elapsed in the 7d window (expected > 1%)
- Only shown on the 7d window

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
- Verify config exists: `cat ~/.config/omcc-statusline/config.json`

**Performance issues:**
- PR/CI fetches happen in background, shouldn't block statusline
- First run may take up to 5s (all caches miss) — subsequent renders use cache
- Limits API is cached for 2 minutes — should not cause slowness
