# OMCC Statusline

Slot-based statusline for Claude Code — limits, git, PR dots, pace indicator.

## Preview

```
my-project/ ⋮ ⑂feat/auth*+ ⋮ 5h ▁ 7d ▃ ctx ▂ ⋮ chill 1%
```
```
my-project/ ⋮ ⑂feat/auth*+ · CI · ⁕⁕⁕⁕ 💬3 ⋮ 5h ▂ 7d ▁ ctx ▂ ⋮ based 28%
```

## Vibe Pacing

The `vibes` block tells you how your API spending is going relative to your 5-day budget window — without making you do math.

During the week you get a **pace label** and a **delta** (how far ahead or behind the expected burn rate you are):

| Label | What it means |
|-------|---------------|
| `depresso` | Way over pace — burning fast |
| `salty` | Slightly over pace |
| `chill` | Right on track, comfortable margin |
| `hyped` | Running a bit under pace |
| `based` | Barely spending anything |

Next to the label you get a signed percentage like `+18%` or `-5%` — positive means you're ahead of pace (good), negative means you're burning faster than expected (watch out). After the first half-day, a **surplus** indicator also appears: `+2.3d` means "at this rate, your budget stretches 2.3 extra days beyond the 5-day window." Negative? You're on borrowed time.

Once the 5 work days have elapsed and you're in weekend territory, pace metrics stop making sense — so the statusline switches to **weekend mode**: the text `no pace police` appears in a slowly cycling rainbow gradient. No judgment, just vibes.

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
