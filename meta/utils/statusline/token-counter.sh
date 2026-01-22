#!/usr/bin/env bash

# ccusage statusline example:
# 🤖 Sonnet 4.5 | 💰 $25.17 session / $25.21 today / $10.76 block (3h 9m left) | 🔥 $5.81/hr 🟢 (Normal) | 🧠 387,071 (194%)

# our statusline example
# oh-my-claude-plugins/ ⑂main • Sonnet 4.5 • sess $25.3 / today $1.7 / total $26.9 • 51%
# ^ cwd
#            git branch ^
#                         model ^
#                                                                free context window ^

# ANSI Colors
BLACK=$'\033[0;30m'
DGRAY=$'\033[1;30m'
RED=$'\033[0;31m'
BRED=$'\033[1;31m'
GREEN=$'\033[0;32m'
BGREEN=$'\033[1;32m'
YELLOW=$'\033[0;33m'
BYELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
BBLUE=$'\033[1;34m'
PURPLE=$'\033[0;35m'
BPURPLE=$'\033[1;35m'
CYAN=$'\033[0;36m'
BCYAN=$'\033[1;36m'
LGRAY=$'\033[0;37m'
WHITE=$'\033[1;37m'
GRAY=$'\033[2;37m'

DIM='\033[2m'
NOCOLOR=$'\033[0m'

# consts
DOT='•'
SEP="${DGRAY}${DOT}${NOCOLOR}"

# Read JSON input from stdin
IFS= read -r -d '' -t 1 input

# Extract basic info from statusline JSON
current_dir="$( jq -r '.workspace.current_dir' <<< "$input" )"
model="$( jq -r '.model.display_name' <<< "$input" )"
dir_name="${current_dir##*/}/"

# Extract context window data
context_size="$( jq -r '.context_window.context_window_size // 0' <<< "$input" )"
current_usage="$( jq '.context_window.current_usage' <<< "$input" )"

# Calculate context usage percentage using current_usage for accuracy
used_context_percent=0
if [[ "$current_usage" != 'null' ]] && [[ "$context_size" != '0' && "$context_size" != 'null' ]]; then
    # Sum all token types in current_usage: input, cache_creation, cache_read
    current_tokens="$( jq '(.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)' <<< "${current_usage}" )"
    if [[ "$current_tokens" != 'null' && "$current_tokens" != '0' ]]; then
        used_context_percent="$( echo "scale=0; ($current_tokens * 100) / $context_size" | bc 2>/dev/null || echo '0' )"
    fi
fi

# Get session data (these ARE available in statusline hook)
session_cost="$( jq -r '.cost.total_cost_usd // 0' <<< "$input" )"
#session_duration_ms="$( jq -r '.cost.total_duration_ms // 0' <<< "$input" )"

# Get git branch if in a git repo
git_branch="$( cd "$current_dir" 2>/dev/null && git branch --show-current 2>/dev/null || echo '' )"

# Function to format cost with dollar sign
function format_cost {
    # args
    local -r cost="$1"

    # vars
    local result='0'

    # consts
    local -r currency='$'

    # code
    case "$cost" in
	''|'null'|'0')		:											;;
	*)					printf -v result '%.1f' "$cost" 2>/dev/null	;;
    esac

    echo "${currency}${result}"
}

# Get usage data with proper date filtering
printf -v today_date '%(%Y%m%d)T' -1
ccusage_statusline=$( bun x ccusage statusline --visual-burn-rate emoji-text <<< "$input" )
today_cost=$(bun x ccusage daily --since "$today_date" --until "$today_date" --json 2>/dev/null | jq -r '.totals.totalCost' 2>/dev/null)
total_cost=$(bun x ccusage daily --since 20240101 --json 2>/dev/null | jq -r '.totals.totalCost' 2>/dev/null)

# Format the costs with colors
session_cost_fmt="$(format_cost "$session_cost")"
today_cost_fmt="$(format_cost "$today_cost")"
total_cost_fmt="$(format_cost "$total_cost")"

# Build usage info
usage_info="sess ${session_cost_fmt} / today ${today_cost_fmt} / total ${total_cost_fmt}"

# Format context usage percentage with color gradient
if (( used_context_percent < 30 )); then
    marker="${GREEN}"
elif (( used_context_percent < 60 )); then
    marker="${YELLOW}"
else
    marker="${RED}"
fi

# Generate final status line with colors
echo -n "${BLUE}${dir_name}${NOCOLOR}"
echo -n "${DIM|${NOCOLOR}"
[[ -n "$git_branch" ]] && echo -n "⑂${DIM}${git_branch}${NOCOLOR}"
echo -n "${DIM}|${NOCOLOR}"
echo "$ccusage_statusline"
echo -n "${DIM}|${NOCOLOR}"
echo -n "ctx ${marker}${used_context_percent}%${NOCOLOR}"
