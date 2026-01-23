#!/usr/bin/env bash
set -euo pipefail

#
# ccusage statusline example:
# 🤖 Sonnet 4.5 | 💰 $25.17 session / $25.21 today / $10.76 block (3h 9m left) | 🔥 $5.81/hr 🟢 (Normal) | 🧠 387,071 (194%)
#
# we prepend it with current directory and git branch:
# oh-my-claude-plugins/ ⑂main
#
# Input JSON structure (anonymized example):
# {
#   "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
#   "transcript_path": "/path/to/.claude/projects/.../session.jsonl",
#   "cwd": "/path/to/project",
#   "model": {"id": "claude-sonnet-4-5-20250929", "display_name": "Sonnet 4.5"},
#   "workspace": {"current_dir": "/path/to/project", "project_dir": "/path/to/project"},
#   "version": "2.1.17",
#   "output_style": {"name": "default"},
#   "cost": {
#     "total_cost_usd": 58.07,
#     "total_duration_ms": 33554050,
#     "total_api_duration_ms": 10338728,
#     "total_lines_added": 2453,
#     "total_lines_removed": 661
#   },
#   "context_window": {
#     "total_input_tokens": 639789,
#     "total_output_tokens": 447533,
#     "context_window_size": 200000,
#     "current_usage": {
#       "input_tokens": 0,
#       "output_tokens": 1,
#       "cache_creation_input_tokens": 146,
#       "cache_read_input_tokens": 57288
#     },
#     "used_percentage": 29,
#     "remaining_percentage": 71
#   },
#   "exceeds_200k_tokens": false
# }
#

function die {
    local -r message="${1:-}"
    local -ri code="${2:-1}"

    echo "FATAL: ${message}"
    exit "$code"
} 1>&2

# consts
# Color constants - many unused but kept for future customization
# shellcheck disable=SC2034
{
    declare -r BLACK=$'\033[0;30m'
    declare -r DGRAY=$'\033[1;30m'
    declare -r RED=$'\033[0;31m'
    declare -r BRED=$'\033[1;31m'
    declare -r GREEN=$'\033[0;32m'
    declare -r BGREEN=$'\033[1;32m'
    declare -r YELLOW=$'\033[0;33m'
    declare -r BYELLOW=$'\033[1;33m'
    declare -r BLUE=$'\033[0;34m'
    declare -r BBLUE=$'\033[1;34m'
    declare -r PURPLE=$'\033[0;35m'
    declare -r BPURPLE=$'\033[1;35m'
    declare -r CYAN=$'\033[0;36m'
    declare -r BCYAN=$'\033[1;36m'
    declare -r LGRAY=$'\033[0;37m'
    declare -r WHITE=$'\033[1;37m'
    declare -r GRAY=$'\033[2;37m'
    declare -r DIM=$'\033[2m'
    declare -r NOCOLOR=$'\033[0m'

    declare -r SEP1=" ${DGRAY}•${NOCOLOR} "
    declare -r SEP2=" ${DGRAY}|${NOCOLOR} "
    declare -r BRANCH_LABEL='⑂'
}

function read_json_input {
    # args
    local -r var_name="$1"

    # vars
    local -n input_ref="$var_name"
    local temp

    # code
    IFS= read -r -d '' -t 1 temp || true

    # result: assign to caller's variable via nameref
    # shellcheck disable=SC2034  # input_ref is a nameref that modifies caller's variable
    input_ref="$temp"
}

function extract_current_dir {
    # args
    local -r input="$1"

    # vars
    local current_dir

    # code
    current_dir=$( jq --raw-output '.workspace.current_dir' <<< "$input" )

    # assert: jq succeeded
    [[ -n "$current_dir" ]] || die "Failed to extract current_dir from JSON"

    # result: current directory path
    echo "$current_dir"
}

function get_dir_name {
    # args
    local -r current_dir="$1"

    # code
    # result: directory basename with trailing slash
    echo "${current_dir##*/}/"
}

function get_git_branch {
    # args
    local -r current_dir="$1"

    # vars
    local git_branch

    # code
    git_branch=$( cd "$current_dir" 2>/dev/null && git branch --show-current 2>/dev/null || echo '' )

    # result: git branch name or empty string
    echo "$git_branch"
}

function get_ccusage_statusline {
    # args
    local -r input="$1"

    # vars
    local ccusage_output

    # code
    ccusage_output=$( bun x ccusage statusline --visual-burn-rate emoji-text <<< "$input" )

    # result: ccusage statusline output
    echo "$ccusage_output"
}

function render_statusline {
    # args
    local -r dir_name="$1"
    local -r git_branch="$2"
    local -r ccusage_statusline="$3"

    # vars
    local git_part

    # code
    git_part=""
    [[ -n "$git_branch" ]] && git_part="${BRANCH_LABEL}${DIM}${git_branch}${NOCOLOR}${SEP2}"

    # result: formatted statusline
    printf '%b%b%b%b\n' \
        "${BLUE}${dir_name}${NOCOLOR}" \
        "${SEP2}" \
        "$git_part" \
        "$ccusage_statusline"
}

function main {
    # vars
    local input current_dir dir_name git_branch ccusage_statusline

    # code
    read_json_input input

    # assert: got input
    [[ -n "$input" ]] || die "No JSON input received from stdin"

    current_dir=$( extract_current_dir "$input" )
    dir_name=$( get_dir_name "$current_dir" )
    git_branch=$( get_git_branch "$current_dir" )
    ccusage_statusline=$( get_ccusage_statusline "$input" )

    render_statusline "$dir_name" "$git_branch" "$ccusage_statusline"
}

main
