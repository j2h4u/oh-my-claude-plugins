#!/usr/bin/env bash
set -euo pipefail

# ccusage statusline example:
# 🤖 Sonnet 4.5 | 💰 $25.17 session / $25.21 today / $10.76 block (3h 9m left) | 🔥 $5.81/hr 🟢 (Normal) | 🧠 387,071 (194%)

# our statusline example:
# oh-my-claude-plugins/ ⑂main • Sonnet 4.5 • sess $25.3 / today $1.7 / total $26.9 • 51%
# ^ cwd
#            git branch ^
#                         model ^
#                                                                free context window ^

function die {
    local -r message="${1:-}"
    local -ri code="${2:-1}"

    echo "FATAL: ${message}" >&2
    exit "$code"
}

# consts
# Color constants - many unused but kept for future customization
# shellcheck disable=SC2034
declare -r BLACK=$'\033[0;30m' DGRAY=$'\033[1;30m' RED=$'\033[0;31m' BRED=$'\033[1;31m'
# shellcheck disable=SC2034
declare -r GREEN=$'\033[0;32m' BGREEN=$'\033[1;32m' YELLOW=$'\033[0;33m' BYELLOW=$'\033[1;33m'
# shellcheck disable=SC2034
declare -r BLUE=$'\033[0;34m' BBLUE=$'\033[1;34m' PURPLE=$'\033[0;35m' BPURPLE=$'\033[1;35m'
# shellcheck disable=SC2034
declare -r CYAN=$'\033[0;36m' BCYAN=$'\033[1;36m' LGRAY=$'\033[0;37m' WHITE=$'\033[1;37m'
# shellcheck disable=SC2034
declare -r GRAY=$'\033[2;37m' DIM=$'\033[2m' NOCOLOR=$'\033[0m'

# shellcheck disable=SC2034
declare -r SEP1=" ${DGRAY}•${NOCOLOR} " SEP2=" ${DGRAY}|${NOCOLOR} "

function read_json_input {
    # vars
    local input

    # code
    IFS= read -r -d '' -t 1 input || true

    # result: JSON input from stdin
    echo "$input"
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

    # code
    echo -en "${BLUE}${dir_name}${NOCOLOR}"
    echo -en "${SEP2}"

    if [[ -n "$git_branch" ]]; then
        echo -en "⑂${DIM}${git_branch}${NOCOLOR}"
        echo -en "${SEP2}"
    fi

    echo -e "$ccusage_statusline"
}

function main {
    # vars
    local input current_dir dir_name git_branch ccusage_statusline

    # code
    input=$( read_json_input )

    # assert: got input
    [[ -n "$input" ]] || die "No JSON input received from stdin"

    current_dir=$( extract_current_dir "$input" )
    dir_name=$( get_dir_name "$current_dir" )
    git_branch=$( get_git_branch "$current_dir" )
    ccusage_statusline=$( get_ccusage_statusline "$input" )

    render_statusline "$dir_name" "$git_branch" "$ccusage_statusline"
}

main
