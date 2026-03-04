# OMCC Statusline

Slot-based statusline for Claude Code — limits, git, PR dots, pace indicator. Each line is a slot: built-in provider or external command.

## Preview

```
my-project/ · ⑂feat/auth*+ · 5h ▁ 7d ▃ ctx ▂ · chill 1%
```
```
my-project/ · ⑂feat/auth*+ CI | ⁕⁕⁕⁕ 💬3 · 5h ▂ 7d ▁ ctx ▂ · based 28%
⬆ /gsd:update │ Fixing auth bug │ █████░░░░░ 52%
```

## Vibe Pace

If you never hit the 7-day limit, you can skip this section — vibe pace isn't for you.

But if you regularly bump into the weekly cap and then sit waiting for the window to roll over, pace helps you spread your budget evenly instead of burning through it in the first couple of days.

The idea is simple. The 7-day window is 168 hours, but nobody works all 168. Pace assumes a **120-hour working budget** (5 days x 24h) and draws a straight line from 0% to 100% across that budget. At any moment it knows where you *should* be on that line, and it compares that to where you *actually* are. The difference (in percentage points) is your delta.

The `vibes` provider turns that delta into a single word in the statusline:

- **based** — 20+ pp under expected. You're way ahead of schedule, plenty of runway left.
- **hyped** — 5–20 pp under. Comfortable margin.
- **chill** — within ±5 pp. Right on track.
- **salty** — 5–20 pp over. You're burning faster than the budget allows.
- **depresso** — 20+ pp over. At this rate you'll hit the wall well before the window resets.

The number after the label (e.g. `chill 1%`, `based 28%`) is the absolute delta in percentage points. Color shifts from green (under budget) to red (over).

Pace is hidden at the start of a new window when there isn't enough data to compute a meaningful expected value.

## Installation

```bash
python3 ~/.claude/plugins/marketplaces/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py --install
```

Test: `python3 omcc-statusline.py --demo`

## Providers

- `path` — Current directory
- `git` — Branch, status (`*+?↑↓`), CI, PR dots (`⁕`), notifications (`💬`)
- `limits` — API usage (5h/7d/ctx bars with color ramps)
- `vibes` — 7d pace (based/hyped/chill/salty/depresso)

## Configuration

`~/.config/omcc-statusline/config.json`:

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

Without `slots` key — default single-line: `path · git · limits · vibes`.

### Slots

- `{"provider": "<name>"}` — built-in (path, git, limits, vibes)
- `{"command": "<shell>"}` — external command (reads JSON stdin, outputs one line)
- `"ttl": <seconds>` — cache lifetime (default: 60s)
- `"enabled": false` — disable without removing
- Array slot = multiple providers joined on one line

### Settings

| Key | Options | Default |
|-----|---------|---------|
| `5h_ramp`, `7d_ramp`, `ctx_ramp` | aurora, traffic, twilight, ember, spectrum, heatmap | spectrum, spectrum, aurora |
| `5h_display`, `7d_display`, `ctx_display` | number, vertical, horizontal | vertical |
| `separator` | any string | · |
| `separator_section` | any string | \| |

`separator` — between providers (extra). `separator_section` — within provider (intra).

## Theme Editor

```bash
python3 omcc-statusline.py --theme
```

`←→` navigate elements, `f`/`b`/`a` edit fg/bg/attrs, `g` settings panel, `c`/`v` copy/paste, `s` save, `q` quit. Ramp/display settings animate the preview bars.

## Troubleshooting

- **Not showing** — `python3 omcc-statusline.py --install`, restart Claude Code
- **Limits empty** — first render fetches in background, appears on second render
- **Old config error** — `bar_ramp` → `5h_ramp`/`7d_ramp`, `bar_style` → `*_display`
- **PR dots missing** — install and auth `gh` CLI
