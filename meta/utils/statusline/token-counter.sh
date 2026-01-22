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
SEP1=" ${DGRAY}•${NOCOLOR} "
SEP2=" ${DGRAY}|${NOCOLOR} "

# Read JSON input from stdin
IFS= read -r -d '' -t 1 input

# Extract basic info from statusline JSON
current_dir="$( jq -r '.workspace.current_dir' <<< "$input" )"
dir_name="${current_dir##*/}/"

# Get git branch if in a git repo
git_branch="$( cd "$current_dir" 2>/dev/null && git branch --show-current 2>/dev/null || echo '' )"

# Get usage data with proper date filtering
ccusage_statusline=$( bun x ccusage statusline --visual-burn-rate emoji-text <<< "$input" )

# Generate final status line with colors
echo -en "${BLUE}${dir_name}${NOCOLOR}"
echo -en "${SEP2}"
[[ -n "$git_branch" ]] && { echo -en "⑂${DIM}${git_branch}${NOCOLOR}"; echo -en "${SEP2}"; }
echo -e "$ccusage_statusline"
