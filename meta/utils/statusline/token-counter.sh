#!/usr/bin/env bash
set -euo pipefail

#
# ccusage statusline example:
# 🤖 Sonnet 4.5 | 💰 $25.17 session / $25.21 today / $10.76 block (3h 9m left) | 🔥 $5.81/hr 🟢 (Normal) | 🧠 387,071 (194%)
#
# we prepend it with current directory, git branch and status:
# oh-my-claude-plugins/ ⑂main*+↑↓ | ...
#
# Git status indicators:
#   *  dirty (unstaged changes)   - yellow dim
#   +  staged changes             - green dim
#   ?  untracked files            - gray
#   ↑  ahead of remote            - cyan
#   ↓  behind remote              - purple
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

# PR status cache constants
declare -r PR_CACHE_DIR="${HOME}/.cache/claude-statusline"
declare -r PR_CACHE_FILE="${PR_CACHE_DIR}/pr-status.json"
declare -r PR_LOCK_FILE="${PR_CACHE_DIR}/refresh.lock"
declare -r GH_AVAILABLE_FILE="${PR_CACHE_DIR}/gh-available"
declare -ri PR_CACHE_TTL=300
declare -ri GH_CHECK_TTL=1800

function check_gh_available {
    # args: caller's variable name to receive status string
    local -r var_name="$1"

    # vars
    local -n status_ref="$var_name"
    local cache_age now cached_ts cached_status

    # code: check cached result first
    if [[ -f "$GH_AVAILABLE_FILE" ]]; then
        cached_ts=$( stat -c '%Y' "$GH_AVAILABLE_FILE" 2>/dev/null ) \
            || cached_ts=$( stat -f '%m' "$GH_AVAILABLE_FILE" 2>/dev/null ) \
            || cached_ts=0
        now=$( date +%s )
        cache_age=$(( now - cached_ts ))
        cached_status=$( < "$GH_AVAILABLE_FILE" )
        if (( cache_age < GH_CHECK_TTL )) && [[ -n "$cached_status" ]]; then
            # shellcheck disable=SC2034  # status_ref is a nameref
            status_ref="$cached_status"
            [[ "$cached_status" == "ok" ]]
            return
        fi
    fi

    # ensure cache dir exists
    mkdir -p "$PR_CACHE_DIR"

    # check gh command exists
    if ! command -v gh &>/dev/null; then
        echo "no-gh" > "$GH_AVAILABLE_FILE"
        # shellcheck disable=SC2034
        status_ref="no-gh"
        return 1
    fi

    # check gh auth
    if ! gh auth status &>/dev/null; then
        echo "no-auth" > "$GH_AVAILABLE_FILE"
        # shellcheck disable=SC2034
        status_ref="no-auth"
        return 1
    fi

    echo "ok" > "$GH_AVAILABLE_FILE"
    # shellcheck disable=SC2034
    status_ref="ok"
    # result: gh is available
    return 0
}

function is_cache_fresh {
    # args
    local -r cache_file="$1"
    local -ri ttl="$2"

    # vars
    local file_ts now cache_age

    # code
    [[ -f "$cache_file" ]] || return 1

    file_ts=$( stat -c '%Y' "$cache_file" 2>/dev/null ) \
        || file_ts=$( stat -f '%m' "$cache_file" 2>/dev/null ) \
        || return 1
    now=$( date +%s )
    cache_age=$(( now - file_ts ))

    # result: 0 if fresh, 1 if stale
    (( cache_age < ttl ))
}

function refresh_pr_cache {
    # code: acquire lock (nonblock), skip if another refresh is running
    exec 9>"$PR_LOCK_FILE"
    flock --nonblock 9 || return 0

    # vars
    local graphql_result notifications_count tmp_file

    # GraphQL: all my open PRs with CI status
    graphql_result=$( gh api graphql -f query='
        query {
            search(query: "is:open is:pr author:@me", type: ISSUE, first: 20) {
                nodes {
                    ... on PullRequest {
                        number
                        repository { nameWithOwner }
                        url
                        commits(last: 1) {
                            nodes {
                                commit {
                                    statusCheckRollup {
                                        state
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    ' 2>/dev/null ) || graphql_result='{}'

    # REST: unread PR+Issue notifications (participating only — excludes repo-wide watches)
    notifications_count=$( gh api notifications --jq '
        [.[] | select(
            (.subject.type == "PullRequest" or .subject.type == "Issue")
            and .unread
            and (.reason == "comment" or .reason == "mention" or .reason == "author" or .reason == "review_requested" or .reason == "assign")
        )] | length
    ' 2>/dev/null ) || notifications_count=0

    # atomic write via temp file + mv
    tmp_file="${PR_CACHE_FILE}.tmp.$$"
    jq -n \
        --argjson prs "$graphql_result" \
        --argjson unread "$notifications_count" \
        '{ prs: $prs, unread_count: $unread, updated_at: now }' \
        > "$tmp_file" 2>/dev/null \
        && mv "$tmp_file" "$PR_CACHE_FILE"

    # release lock
    exec 9>&-
}

function make_osc8_link {
    # args
    local -r url="$1"
    local -r text="$2"

    # result: OSC 8 hyperlink escape sequence
    # shellcheck disable=SC1003  # backslashes are intentional OSC 8 ST (String Terminator)
    printf '\e]8;;%s\e\\%s\e]8;;\e\\' "$url" "$text"
}

function get_pr_status {
    # consts
    local -r PR_DOT='⁕'

    # vars
    local gh_status='' cache_json pr_nodes
    local total_prs ci_state pr_url dot
    local unread_count output=''

    # code: check if gh is available (from cache)
    if ! check_gh_available gh_status; then
        case "$gh_status" in
            no-gh)   echo "${RED}gh not installed${NOCOLOR}" ;;
            no-auth) echo "${RED}gh auth login${NOCOLOR}" ;;
        esac
        return 0
    fi

    # ensure cache dir exists
    mkdir -p "$PR_CACHE_DIR"

    # if cache is stale or missing, trigger background refresh
    if ! is_cache_fresh "$PR_CACHE_FILE" "$PR_CACHE_TTL"; then
        refresh_pr_cache &
        disown
    fi

    # read cache (if it exists)
    [[ -f "$PR_CACHE_FILE" ]] || return 0
    cache_json=$( < "$PR_CACHE_FILE" )
    [[ -n "$cache_json" ]] || return 0

    # parse PR data
    total_prs=$( jq -r '.prs.data.search.nodes | length' <<< "$cache_json" 2>/dev/null ) || total_prs=0
    (( total_prs > 0 )) || return 0

    # collect dots per CI state, sorted by severity: red → yellow → green → gray
    pr_nodes=$( jq -r '.prs.data.search.nodes' <<< "$cache_json" 2>/dev/null ) || return 0
    local dots_red='' dots_pending='' dots_green='' dots_gray=''

    local i
    for (( i = 0; i < total_prs; i++ )); do
        ci_state=$( jq -r ".[$i].commits.nodes[0].commit.statusCheckRollup.state // \"UNKNOWN\"" <<< "$pr_nodes" 2>/dev/null ) || ci_state="UNKNOWN"
        pr_url=$( jq -r ".[$i].url // empty" <<< "$pr_nodes" 2>/dev/null ) || pr_url=""

        dot=$( make_osc8_link "$pr_url" "${PR_DOT}" )
        case "$ci_state" in
            FAILURE|ERROR)    dots_red+="$dot" ;;
            PENDING|EXPECTED) dots_pending+="$dot" ;;
            SUCCESS)          dots_green+="$dot" ;;
            *)                dots_gray+="$dot" ;;
        esac
    done

    # assemble: red → yellow → green → gray (each cluster in its color)
    [[ -n "$dots_red" ]]    && output+="${RED}${dots_red}${NOCOLOR}"
    [[ -n "$dots_pending" ]] && output+="${BLUE}${dots_pending}${NOCOLOR}"
    [[ -n "$dots_green" ]]  && output+="${GREEN}${dots_green}${NOCOLOR}"
    [[ -n "$dots_gray" ]]   && output+="${DGRAY}${dots_gray}${NOCOLOR}"

    # append unread comment count
    unread_count=$( jq -r '.unread_count // 0' <<< "$cache_json" 2>/dev/null ) || unread_count=0
    if (( unread_count > 0 )); then
        output+=" ${CYAN}💬${unread_count}${NOCOLOR}"
    fi

    # result: formatted PR status string
    echo "$output"
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

    # assert: jq succeeded and returned a real path (not jq's "null" for missing keys)
    [[ -n "$current_dir" && "$current_dir" != "null" ]] || die "Failed to extract current_dir from JSON"

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
    git_branch=$( git -C "$current_dir" branch --show-current 2>/dev/null ) || git_branch=''

    # result: git branch name or empty string
    echo "$git_branch"
}

function get_git_status {
    # args
    local -r current_dir="$1"

    # vars
    local status_output header_line file_lines indicators=''
    local ahead='' behind='' dirty='' staged='' untracked=''

    # code: run git in subshell to avoid changing cwd
    status_output=$( git -C "$current_dir" status --porcelain=v1 --branch 2>/dev/null ) || {
        echo
        return
    }

    # split: first line is header (## branch...tracking), rest are file statuses
    header_line="${status_output%%$'\n'*}"
    file_lines="${status_output#*$'\n'}"

    # parse ahead/behind from header: ## main...origin/main [ahead 2, behind 3]
    [[ "$header_line" =~ ahead\ ([0-9]+) ]] && ahead="${BASH_REMATCH[1]}"
    [[ "$header_line" =~ behind\ ([0-9]+) ]] && behind="${BASH_REMATCH[1]}"

    # parse file statuses (XY format: X=staged, Y=unstaged)
    # check both start of string and after newlines for multiline output
    [[ "$file_lines" =~ (^|$'\n')[MADRC] ]] && staged="+"
    [[ "$file_lines" =~ (^|$'\n').[MD] ]] && dirty="*"
    [[ "$file_lines" =~ (^|$'\n')\?\? ]] && untracked="?"

    # build colored indicators (order: dirty staged untracked ahead behind)
    [[ -n "$dirty" ]] && indicators+="${DIM}${YELLOW}*${NOCOLOR}"
    [[ -n "$staged" ]] && indicators+="${DIM}${GREEN}+${NOCOLOR}"
    [[ -n "$untracked" ]] && indicators+="${DIM}${GRAY}?${NOCOLOR}"
    [[ -n "$ahead" ]] && indicators+="${CYAN}↑${NOCOLOR}"
    [[ -n "$behind" ]] && indicators+="${PURPLE}↓${NOCOLOR}"

    # result: formatted git status string
    echo "$indicators"
}

function get_ccusage_statusline {
    # args
    local -r input="$1"

    # vars
    local ccusage_output

    # code
    if ! command -v bun &>/dev/null; then
        echo "${RED}bun not found${NOCOLOR}"
        return 0
    fi

    ccusage_output=$( bun x ccusage statusline --visual-burn-rate text --refresh-interval 60 <<< "$input" 2>/dev/null ) || {
        echo "${RED}ccusage error${NOCOLOR}"
        return 0
    }

    # result: ccusage statusline output
    echo "$ccusage_output"
}

function render_statusline {
    # args
    local -r dir_name="$1"
    local -r git_branch="$2"
    local -r git_status="$3"
    local -r pr_status="$4"
    local -r ccusage_statusline="$5"

    # vars
    local git_part pr_part

    # code
    git_part=''
    if [[ -n "$git_branch" ]]; then
        git_part=" ${BRANCH_LABEL}${DIM}${git_branch}${NOCOLOR}"
        [[ -n "$git_status" ]] && git_part+="${git_status}"
    fi

    pr_part=''
    if [[ -n "$pr_status" ]]; then
        pr_part="${SEP2}${pr_status}"
    fi

    # result: two-line statusline
    # line 1: ccusage (model, costs, burn rate, context)
    # line 2: dir + git + PR status
    printf '%s\n%s%s%s\n' \
        "$ccusage_statusline" \
        "${DIM}${dir_name}${NOCOLOR}" \
        "$git_part" \
        "$pr_part"
}

function demo_statusline {
    # consts
    local -r D='⁕'

    # code: render demo scenarios with synthetic data
    echo "=== Demo: all green ==="
    render_statusline \
        "my-project/" \
        "main" \
        "${DIM}${GREEN}+${NOCOLOR}" \
        "${GREEN}${D}${D}${D}${NOCOLOR}" \
        "🤖 Sonnet 4.5 ${DGRAY}|${NOCOLOR} 💰 \$12.34 session"

    echo "=== Demo: mixed CI + unread comments ==="
    render_statusline \
        "my-project/" \
        "feat/auth" \
        "${DIM}${YELLOW}*${NOCOLOR}${DIM}${GREEN}+${NOCOLOR}" \
        "${RED}${D}${NOCOLOR}${BLUE}${D}${D}${NOCOLOR}${GREEN}${D}${D}${NOCOLOR}${DGRAY}${D}${NOCOLOR} ${CYAN}💬3${NOCOLOR}" \
        "🤖 Opus 4.6 ${DGRAY}|${NOCOLOR} 💰 \$58.07 session"

    echo "=== Demo: gh not installed ==="
    render_statusline \
        "my-project/" \
        "main" \
        "" \
        "${RED}gh not installed${NOCOLOR}" \
        "🤖 Sonnet 4.5 ${DGRAY}|${NOCOLOR} 💰 \$0.42 session"

    echo "=== Demo: bun not found ==="
    render_statusline \
        "my-project/" \
        "develop" \
        "${CYAN}↑${NOCOLOR}" \
        "" \
        "${RED}bun not found${NOCOLOR}"
}

function main {
    # code: handle --demo flag
    if [[ "${1:-}" == "--demo" ]]; then
        demo_statusline
        return 0
    fi

    # vars
    local input ccusage_statusline
    local current_dir dir_name
    local git_branch git_status pr_status

    # code
    read_json_input input

    # assert: got input
    [[ -n "$input" ]] || die "No JSON input received from stdin"

    current_dir=$( extract_current_dir "$input" )
    dir_name=$( get_dir_name "$current_dir" )
    git_branch=$( get_git_branch "$current_dir" )
    git_status=$( get_git_status "$current_dir" )
    pr_status=$( get_pr_status )
    ccusage_statusline=$( get_ccusage_statusline "$input" )

    render_statusline "$dir_name" "$git_branch" "$git_status" "$pr_status" "$ccusage_statusline"
}

main "$@"
