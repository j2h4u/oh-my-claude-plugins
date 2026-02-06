# Custom Statusline for Claude Code

Enhanced statusline that prepends directory name, git branch, and PR status to `ccusage` output.

## Preview

```
oh-my-claude-plugins/ ⑂main*+ | PR 7 | 🤖 Sonnet 4.5 | 💰 $25.17 session / ...
```

**With CI failure + unread comments:**
```
oh-my-claude-plugins/ ⑂main*+ | PR 7 #9997 💬2 | 🤖 Sonnet 4.5 | ...
```

**Format:**
```
<dir_name>/ ⑂<git_branch><status> | PR <count> [#failed...] [💬N] | <ccusage output>
```

- **oh-my-claude-plugins/** — Current directory name (blue)
- **⑂main** — Git branch (dimmed, only shown if in git repo)
- **PR 7** — Open PR count (green=ok, yellow=pending, red=failure). Clickable → github.com/pulls
- **#9997** — Failed PR numbers (red). Clickable → PR page. Only shown on CI failure
- **💬2** — Unread PR comment count (cyan). Only shown when > 0
- **Rest** — Output from [`ccusage`](https://github.com/ryoppippi/ccusage) statusline with costs, burn rate, and context usage

If `gh` is not installed, shows `gh not installed` in red. If not authenticated, shows `gh auth login` in red. The PR section is hidden when there are 0 open PRs.

## Requirements

- `jq` — JSON processing
- `bun` — For running ccusage
- [`ccusage`](https://github.com/ryoppippi/ccusage) — Claude Code usage tracker
- [`gh`](https://cli.github.com/) — GitHub CLI (optional, for PR status indicator)

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
4. **Gets PR status** — Checks cached GitHub PR data (see below)
5. **Delegates to ccusage** — Passes JSON to `ccusage statusline --visual-burn-rate emoji-text`
6. **Formats output** — Prepends directory + branch + PR status with color coding and separators

### PR Status Caching

PR data is cached to avoid blocking the statusline render:

- **Cache directory:** `~/.cache/claude-statusline/`
- **Cache TTL:** 5 minutes (300s) for PR data, 30 minutes for `gh` availability check
- **Background refresh:** When cache is stale, a background process fetches new data via `gh` GraphQL/REST API
- **Lock file:** `flock --nonblock` prevents parallel refresh processes
- **Atomic writes:** Cache updates use temp file + `mv` to avoid partial reads
- **First run:** PR section is hidden until the first background refresh completes

PR links use OSC 8 terminal hyperlinks — clickable in modern terminals (iTerm2, WezTerm, kitty, Windows Terminal).

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

**PR status not showing:**
- Requires `gh` CLI installed and authenticated (`gh auth login`)
- Hidden when you have 0 open PRs
- First render after cache expires may show stale data (refreshes in background)
- Check cache: `cat ~/.cache/claude-statusline/pr-status.json | jq`
- Force refresh: `rm -rf ~/.cache/claude-statusline/`
