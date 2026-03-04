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

## Installation

```bash
python3 ~/.claude/plugins/marketplaces/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py --install
```

Test: `python3 omcc-statusline.py --demo`

## Providers

- `path` — Current directory
- `git` — Branch, status (`*+?↑↓`), CI, PR dots (`⁕`), notifications (`💬`)
- `limits` — API usage (5h/7d/ctx bars with color ramps)
- `vibes` — 7d pace (vibing/chill/ok/easy/based/brake)

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
