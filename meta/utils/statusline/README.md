# OMCC Statusline

Slot-based statusline for Claude Code — limits, git, PR dots, pace indicator.

## Preview

```
my-project/ ⋮ ⑂feat/auth*+ ⋮ 5h ▁ 7d ▃ ctx ▂ ⋮ chill 1%
```
```
my-project/ ⋮ ⑂feat/auth*+ · CI · ⁕⁕⁕⁕ 💬3 ⋮ 5h ▂ 7d ▁ ctx ▂ ⋮ based 28%
```

## Installation

```bash
python3 ~/.claude/plugins/marketplaces/oh-my-claude-plugins/meta/utils/statusline/omcc-statusline.py --install
```

Test: `python3 omcc-statusline.py --demo`

## What You See

- **Directory** — current path
- **Git** — branch, dirty/staged/untracked indicators, CI status, PR dots, notifications
- **Limits** — 5h / 7d / context usage bars with color ramps
- **Vibe Pace** — are you burning your 7-day budget too fast or staying on track?

Pace labels: **based** (way under) → **hyped** → **chill** (on track) → **salty** → **depresso** (way over). Hidden at the start of a new window.

## Configuration

Copy `config.example.json` to `~/.config/omcc-statusline/config.json` and edit. Without config — defaults work out of the box.

External commands that aren't installed show a dim placeholder (e.g. `[ccusage: not found]`).

## Theme Editor

```bash
python3 omcc-statusline.py --theme
```

Navigate elements, tweak colors, adjust separators and ramp styles — all with live preview.

## Troubleshooting

- **Not showing** — run `--install`, restart Claude Code
- **Limits empty** — fetched in background, appears on next render
- **PR dots missing** — install and auth `gh` CLI
