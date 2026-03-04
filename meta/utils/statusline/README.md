# OMCC Statusline — Slot-based multi-line statusline with limits, git, and PR dots

Enhanced statusline for Claude Code with a **slot system** — each line is a slot that can be a built-in provider or an external command. Supports N lines, backward compatible.

## Preview

**Default single-line (path · git · limits · vibes):**
```
my-project/ · ⑂feat/auth*+ · 5h ▁ 7d ▃ ctx ▂ · chill 1%
```

**5h exhausted (red), 7d for context:**
```
my-project/ · ⑂feat/auth* CI | ⁕⁕ · 5h █22m 7d ▆1d 4h ctx ▆ · based 20%
```

**2-line with GSD slot (external command):**
```
my-project/ · ⑂feat/auth*+ CI | ⁕⁕⁕⁕ 💬3 · 5h ▂ 7d ▁ ctx ▂ · based 28%
⬆ /gsd:update │ Fixing auth bug │ █████░░░░░ 52%
```

### Slot System

Each slot is either a **built-in provider** or an **external command**. Slots run in parallel for speed.

**Built-in providers:**
- `path` — Current directory (parent/current/)
- `git` — Branch + git status + CI + PR dots + notifications
- `limits` — API usage limits (5h/7d windows) + context window utilization
- `vibes` — 7d pace indicator (vibing/chill/ok/easy/based/brake)

**Composable slots:** A slot can be a list of providers joined on one line:
```json
{"slots": [[{"provider": "path"}, {"provider": "git"}, {"provider": "limits"}]]}
```

**External commands:** Any shell command that reads JSON from stdin and outputs one line to stdout. Executed as fire-and-forget background subprocesses with flock.

### Limits Indicators

Each indicator (5h, 7d, ctx) has independent **display mode** and **color ramp**:

**Display modes** (`5h_display`, `7d_display`, `ctx_display`):
- `vertical` (default) — Single vbar char: `5h ▅`
- `horizontal` — 5-char progress bar: `5h ██▎  `
- `number` — Colored percentage: `5h 42%`

**Color ramp presets** (`5h_ramp`, `7d_ramp`, `ctx_ramp`):
| Preset | Colors | Default for |
|--------|--------|-------------|
| `spectrum` | green→cyan→blue→magenta→red | 5h, 7d |
| `aurora` | cyan→blue→magenta→red | ctx |
| `traffic` | green→yellow→red | — |
| `twilight` | blue→purple→red | — |
| `ember` | dim cyan→dim yellow→dim red | — |
| `heatmap` | blue→cyan→green→yellow→red | — |

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

The **`↑` / `↓`** suffix shows how many percentage points above/below expected pace.
Pace is hidden at session start when not enough time has elapsed.

### Git Elements

- **dir/** — Current directory (muted gray)
- **⑂main** — Git branch indicator + branch name
- **`* + ? ↑ ↓`** — Git status: dirty, staged, untracked, ahead, behind
- **CI** — Current branch CI status (color: 🟢 green | 🔴 red | 🔵 blue)
- **⁕⁕⁕** — PR dots (one dot per open PR, color = CI state)
- **💬3** — Unread notifications (cyan, only shown when > 0)

### Separators

Two separator types, both independently configurable:
- **Sep extra** (`separator`) — Between providers: `path · git · limits`
- **Sep intra** (`separator_section`) — Within a provider: `git | PR`

## Requirements

- **Python 3.10+** — Runtime for statusline renderer
- **Claude Code OAuth** — Limits provider reads token from `~/.claude/.credentials.json`
- **`gh`** (optional) — GitHub CLI for PR indicators

## Installation

**Quick install** (writes to `~/.claude/settings.json`):
```bash
python3 ~/.claude/plugins/marketplaces/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py --install
```

**Manual:** Add to `~/.claude/settings.json`:
```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/plugins/marketplaces/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py"
  }
}
```

### Configure

Config file: `~/.config/omcc-statusline/config.json`

```json
{
  "slots": [
    [{"provider": "path"}, {"provider": "git"}, {"provider": "limits"}, {"provider": "vibes"}],
    {"command": "node ~/.claude/hooks/gsd-statusline.js"}
  ],
  "settings": {
    "5h_ramp": "traffic",
    "ctx_display": "horizontal"
  }
}
```

**Slot options:**
- `{"provider": "<name>"}` — Built-in provider (path, git, limits, vibes)
- `{"command": "<shell cmd>"}` — External command
- `"ttl": <seconds>` — Cache lifetime for commands (default: 60s)
- `"enabled": false` — Disable without removing

**No `slots` key** = default single-line: `path · git · limits · vibes`.

**Settings keys:**

| Key | Options | Default |
|-----|---------|---------|
| `5h_ramp` | aurora/traffic/twilight/ember/spectrum/heatmap | spectrum |
| `7d_ramp` | same | spectrum |
| `ctx_ramp` | same | aurora |
| `5h_display` | number/vertical/horizontal | vertical |
| `7d_display` | same | vertical |
| `ctx_display` | same | vertical |
| `separator` | any string | · |
| `separator_section` | any string | \| |

### Test

```bash
python3 omcc-statusline.py --demo      # Show all scenarios + ramp presets
echo '{}' | python3 omcc-statusline.py  # Test with real data
```

## Theme Editor

Interactive TUI for customizing colors, text attributes, and settings:

```bash
python3 omcc-statusline.py --theme
```

**Navigation mode:**
- **← →** Navigate elements (dir, branch, git status, CI, PR, limits, etc.)
- **f** Pick foreground color (256-color palette with live preview)
- **b** Pick background color
- **a** Toggle text attributes (dim, bold, italic, underline, etc.)
- **g** Global settings (ramps, display modes, separators)
- **c/v** Copy/paste element style
- **s** Save config
- **r/R** Reset element / all to defaults
- **q** Quit

**Settings panel** (`g`): Navigate ramp/display settings with ←→. When a ramp or display setting is focused, the limit bars in the preview animate 0%→100%→0% to show the color gradient in real time.

## How It Works

1. **Reads JSON from Claude Code stdin** — workspace directory, model, tokens, costs
2. **Loads slot config** from `~/.config/omcc-statusline/config.json` (or defaults)
3. **Executes all slots in parallel** via thread pool
4. **Each slot produces one line** — empty lines are filtered out
5. **Returns styled multi-line output** — ANSI colors based on theme config

### Caching

- **Limits cache TTL:** 2 minutes
- **PR cache TTL:** 5 minutes
- **CI cache TTL:** 2 minutes
- **GH availability check TTL:** 30 minutes
- **Background refresh:** When cache is stale, a detached subprocess fetches new data
- **Lock file:** File-level lock prevents parallel refresh
- **Atomic writes:** Temp file + `os.replace()` ensures no partial reads

## Troubleshooting

**Statusline not showing:**
- Check `~/.claude/settings.json` syntax (use absolute path)
- Run `python3 omcc-statusline.py --install` to auto-configure
- Test: `echo '{}' | python3 omcc-statusline.py --demo`

**Limits not showing:**
- First render is always empty (background fetch) — appears on second render
- Force refresh: `rm /tmp/omcc-statusline/limits-cache.json`

**Pace not showing:**
- Hidden until enough time elapsed in the 7d window (expected > 1%)

**PR dots not showing:**
- Requires `gh` CLI installed and authenticated
- Force refresh: `rm -rf /tmp/omcc-statusline/`

**Old config error** (`bar_ramp`, `bar_style`):
- These keys were renamed. Migrate:
  - `bar_ramp` → `5h_ramp` and `7d_ramp`
  - `bar_style` → `5h_display`, `7d_display`, `ctx_display`
