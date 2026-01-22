#!/usr/bin/env bash

# ANSI Colors
BLUE='\033[34m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
CYAN='\033[36m'
DIM='\033[2m'
RESET='\033[0m'

# Read JSON input from stdin
#input="$( cat )"
IFS= read -r -d '' -t 1 input < /dev/stdin

# Extract basic info from statusline JSON
current_dir="$( jq -r '.workspace.current_dir' <<< "$input" )"
model="$( jq -r '.model.display_name' <<< "$input" )"
dir_name="$( basename "$current_dir" )"

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
	''|'null'|'0')		:						;;
	*)			printf -v result '%.1f' "$cost" 2>/dev/null	;;
    esac

    echo "${currency}${result}"
}

# Get usage data with proper date filtering
printf -v today_date '%(%Y%m%d)T' -1
today_cost=$(bun x ccusage daily --since "$today_date" --until "$today_date" --json 2>/dev/null | jq -r '.totals.totalCost' 2>/dev/null)
total_cost=$(bun x ccusage daily --since 20240101 --json 2>/dev/null | jq -r '.totals.totalCost' 2>/dev/null)

# Format the costs with colors
session_cost_fmt="${GREEN}$(format_cost "$session_cost")${RESET}"
today_cost_fmt="$(format_cost "$today_cost")"
total_cost_fmt="${DIM}$(format_cost "$total_cost")${RESET}"

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
context_fmt="${marker}${used_context_percent}%${RESET}"

# Generate final status line with colors
if [ -n "$git_branch" ]; then
    printf "%s ${BLUE}%s/${RESET} ⑂${DIM}%s${RESET} • ${CYAN}%s${RESET} • %b • %b" "${DEBUG}" "$dir_name" "$git_branch" "$model" "$usage_info" "$context_fmt"
else
    printf "${BLUE}%s/${RESET} • ${CYAN}%s${RESET} • %b • %b" "$dir_name" "$model" "$usage_info" "$context_fmt"
fi
