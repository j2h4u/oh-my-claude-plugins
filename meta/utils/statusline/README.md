# Custom Statusline for Claude Code

Enhanced statusline that prepends directory name and git branch to `ccusage` output.

## Preview

```
oh-my-claude-plugins/ ⑂main | 🤖 Sonnet 4.5 | 💰 $25.17 session / $25.21 today / $10.76 block (3h 9m left) | 🔥 $5.81/hr 🟢 (Normal) | 🧠 387,071 (194%)
```

**Format:**
```
<dir_name>/ ⑂<git_branch> | <ccusage output>
```

- **oh-my-claude-plugins/** — Current directory name (blue)
- **⑂main** — Git branch (dimmed, only shown if in git repo)
- **Rest** — Output from [`ccusage`](https://github.com/ryoppippi/ccusage) statusline with costs, burn rate, and context usage

## Requirements

- `jq` — JSON processing
- `bun` — For running ccusage
- [`ccusage`](https://github.com/ryoppippi/ccusage) — Claude Code usage tracker

### Install dependencies

```bash
# macOS
brew install jq

# Debian/Ubuntu
sudo apt install jq

# bun (if not installed)
curl -fsSL https://bun.sh/install | bash

# ccusage runs via bunx, no install needed
```

## Installation

1. Copy script to Claude config:

```bash
cp token-counter.sh ~/.claude/
chmod +x ~/.claude/token-counter.sh
```

2. Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/token-counter.sh"
  }
}
```

3. Restart Claude Code.

## How It Works

1. **Receives JSON from Claude Code** via stdin containing workspace info (current directory, git status, model, tokens, costs)
2. **Extracts directory name** — Shows basename with trailing slash
3. **Gets git branch** (if in repo) — Safely checks current branch
4. **Delegates to ccusage** — Passes JSON to `ccusage statusline --visual-burn-rate emoji-text`
5. **Formats output** — Prepends directory + branch with color coding and separators

All done following dignified-bash standards:
- Strict mode (`set -euo pipefail`)
- Structured functions with sections (`# args`, `# vars`, `# code`, `# result`)
- Proper error handling with `die()` function
- Assertions with comments
- Shellcheck compliant

## Customization

Edit color constants in the script:

```bash
declare -r BLUE=$'\033[0;34m'      # Directory name color
declare -r DIM=$'\033[2m'          # Git branch dim effect
declare -r SEP2=" ${DGRAY}|${NOCOLOR} "  # Separator style
declare -r BRANCH_LABEL='⑂'        # Git branch symbol
```

All ANSI colors are defined but only a few are used. Others kept for easy customization.

## Troubleshooting

**Statusline not showing:**
- Check `~/.claude/settings.json` syntax
- Verify script is executable: `chmod +x ~/.claude/token-counter.sh`
- Test manually: `echo '{"workspace":{"current_dir":"'$(pwd)'"}}' | bash ~/.claude/token-counter.sh`

**ccusage errors:**
- Ensure bun is installed and in PATH
- Try manually: `bun x ccusage --help`

**Git branch not showing:**
- Only displays when in a git repository
- Check: `git branch --show-current` in your project
