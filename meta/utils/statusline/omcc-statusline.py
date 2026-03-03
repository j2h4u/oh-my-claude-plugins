#!/usr/bin/env python3
"""Claude Code statusline — slot-based multi-line statusline.

Reads JSON from stdin (Claude Code statusline protocol), renders N lines
via a slot system. Each slot is either a built-in provider (limits, git) or
an external shell command. Slots are configured in config.json under "slots".

Default (no config): line 1 = limits (5h/7d usage), line 2 = dir + git + CI + PR.

Git status indicators:
  *  dirty (unstaged changes)   — yellow dim
  +  staged changes             — green dim
  ?  untracked files            — gray
  ↑  ahead of remote            — cyan
  ↓  behind remote              — purple
"""

import hashlib
import json
import os
import re
import shutil
import signal
import sys
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# --- constants ---------------------------------------------------------------

# Display
PARENT_DIR_MAX_LEN = 15
BRANCH_LABEL = "⑂"
PR_DOT = "⁕"

# Demo/example data (used in --demo mode)
DEMO_DIR_NAME = "my-project/"
DEMO_BRANCH_MAIN = "feature/wonderful-new-feature"
DEMO_BRANCH_FEATURE = "feat/auth"
DEMO_BRANCH_DEV = "develop"

# Cache TTLs (seconds)
PR_CACHE_TTL = 300       # 5 min
CI_CACHE_TTL = 120       # 2 min
GH_CHECK_TTL = 1800      # 30 min

# Timeouts (seconds) - by operation type
TIMEOUT_SUBPROCESS = 5   # default for run() helper function
TIMEOUT_GIT = 3          # git status (local operation, fast)
TIMEOUT_GH_API = 15      # all GitHub API calls (GraphQL, REST)
# GitHub API limits
GH_PR_FETCH_LIMIT = 20   # max PRs to fetch in GraphQL query

# Error message truncation
STDERR_MAX_LEN = 50      # max stderr length in error messages

# Paths
CACHE_DIR = Path("/tmp") / "omcc-statusline"
THEME_FILE = Path.home() / ".config" / "omcc-statusline" / "config.json"
PR_CACHE_FILE = CACHE_DIR / "pr-status.json"
PR_LOCK_FILE = CACHE_DIR / "refresh.lock"
GH_AVAILABLE_FILE = CACHE_DIR / "gh-available"
CI_CACHE_DIR = CACHE_DIR / "ci"
SLOT_CACHE_DIR = CACHE_DIR / "slots"
SLOT_TIMEOUT = 120           # bg subprocess timeout (not blocking — just prevents zombies)
SLOT_CACHE_TTL = 60          # seconds — how often to re-run external slot commands

# Limits provider
LIMITS_CACHE_FILE = CACHE_DIR / "limits-cache.json"
LIMITS_LOCK_FILE = CACHE_DIR / "limits-refresh.lock"
LIMITS_CACHE_TTL = 120
LIMITS_HTTP_TIMEOUT = 5
LIMITS_API_URL = "https://api.anthropic.com/api/oauth/usage"
LIMITS_CREDS_FILE = Path.home() / ".claude" / ".credentials.json"
LIMITS_BAR_WIDTH = 5
LIMITS_WINDOW_SECONDS = 7 * 24 * 3600   # 7-day window duration in seconds
LIMITS_PACE_BUDGET_HOURS = 120           # 5 working days × 24h — pace budget
LIMITS_COUNTDOWN_THRESHOLD = 50         # show reset countdown above this utilization %
LIMITS_PACE_MIN_EXPECTED = 1            # skip pace label until expected > this %
# Pace scale: (max_delta_pp, label) — sorted ascending, first match wins.
# delta = utilization - expected; negative = under budget (good), positive = over (bad).
# Logarithmic around zero: tight ±5 for chill, wider ±20 for extremes.
# based ←(−20)— hyped ←(−5)— chill ←(+5)— salty ←(+20)— depresso
PACE_SCALE = [
    (-20, "based"),              # 20+ pp under expected
    ( -5, "hyped"),              # 5–20 pp under
    (  5, "chill"),              # ±5 pp — on track
    ( 20, "salty"),              # 5–20 pp over
    (float("inf"), "depresso"),  # 20+ pp over expected
]
# Color ramp endpoints in 256-color RGB cube (index = 16 + 36*R + 6*G + B).
# Each tuple: (dim, bright) — the two ends for interpolation.
RAMP_CYAN   = (23, 51)    # rgb_011 → rgb_055
RAMP_ORANGE = (58, 202)   # rgb_110 → rgb_510
# Pace delta: log scale, max delta for full brightness
PACE_COLOR_MAX_DELTA = 40  # pp — above this = brightest
# Context window: effective range for color mapping
CTX_COLOR_RANGE = (10, 80) # below 10% = dimmest cyan, above 80% = brightest orange
# Unicode block elements: index 0 = empty, 1..7 = 1/8..7/8, 8 = full
_BAR_EIGHTHS = " ▏▎▍▌▋▊▉█"

DEFAULT_SLOTS = [{"provider": "limits"}, {"provider": "git"}]


# --- colors ------------------------------------------------------------------
# Layer 1: Pal — full 256-color ANSI palette, named by appearance.
# Layer 2: T   — semantic theme tokens, named by purpose. Render code uses T only.
#
# 256-color map:
#   0-7    basic:     Pal.black … Pal.white
#   8-15   bright:    Pal.hi_black … Pal.hi_white
#   16-231 RGB cube:  Pal.rgb_RBG  (R,G,B ∈ 0..5)
#   232-255 grayscale: Pal.gray_0 … Pal.gray_23

class Pal:
    """Full 256-color ANSI palette + SGR modifiers."""

    # --- SGR modifiers (combine with any color) ---
    dim  = "\033[2m"
    bold = "\033[1m"
    R    = "\033[0m"

    # --- basic (0-7) ---
    black   = "\033[38;5;0m"
    red     = "\033[38;5;1m"
    green   = "\033[38;5;2m"
    yellow  = "\033[38;5;3m"
    blue    = "\033[38;5;4m"
    magenta = "\033[38;5;5m"
    cyan    = "\033[38;5;6m"
    white   = "\033[38;5;7m"

    # --- bright (8-15) ---
    hi_black   = "\033[38;5;8m"
    hi_red     = "\033[38;5;9m"
    hi_green   = "\033[38;5;10m"
    hi_yellow  = "\033[38;5;11m"
    hi_blue    = "\033[38;5;12m"
    hi_magenta = "\033[38;5;13m"
    hi_cyan    = "\033[38;5;14m"
    hi_white   = "\033[38;5;15m"

    # --- RGB cube (16-231) and grayscale (232-255) generated below ---


# RGB cube: Pal.rgb_000 .. Pal.rgb_555  (216 colors)
for _r in range(6):
    for _g in range(6):
        for _b in range(6):
            setattr(Pal, f"rgb_{_r}{_g}{_b}", f"\033[38;5;{16 + 36*_r + 6*_g + _b}m")

# Grayscale ramp: Pal.gray_0 (#080808) .. Pal.gray_23 (#eeeeee)
for _i in range(24):
    setattr(Pal, f"gray_{_i}", f"\033[38;5;{232 + _i}m")

del _r, _g, _b, _i


class T:
    """Semantic theme tokens — the only colors render code should reference."""
    # directory
    dir_parent     = Pal.gray_7            # muted parent path
    dir_name       = Pal.gray_6            # current dir (step darker than parent)
    # git branch
    branch_sign    = Pal.gray_6            # ⑂ symbol
    branch_name    = Pal.gray_6            # branch text
    # git working tree indicators
    git_dirty      = Pal.dim + Pal.yellow  # * unstaged changes
    git_staged     = Pal.dim + Pal.green   # + staged changes
    git_untracked  = Pal.gray_3            # ? new files
    git_ahead      = Pal.cyan              # ↑ ahead of remote
    git_behind     = Pal.magenta           # ↓ behind remote
    # CI status (color IS the indicator, no glyphs)
    ci_ok          = Pal.green
    ci_fail        = Pal.red
    ci_wait        = Pal.blue
    # PR dots
    pr_ok          = Pal.green
    pr_fail        = Pal.red
    pr_wait        = Pal.blue
    pr_none        = Pal.hi_black          # no CI / unknown
    # notifications
    notif          = Pal.cyan
    # UI chrome
    sep            = Pal.hi_black          # | separator
    err            = Pal.red               # error messages
    # limits
    lim_time       = Pal.gray_6            # reset time
    lim_bar_bg     = "\033[48;5;236m"      # dark gray background for bar (color236)
    # reset shorthand
    R              = Pal.R


SEP2 = f" {T.sep}|{T.R} "
SEP_DOT = f" {T.sep}·{T.R} "  # separator between limits sections


# --- theme config loading ----------------------------------------------------

_ATTR_SGR = {
    "none": "", "dim": "\033[2m", "bold": "\033[1m", "italic": "\033[3m",
    "underline": "\033[4m", "ul_double": "\033[21m", "ul_curly": "\033[4:3m",
    "ul_dotted": "\033[4:4m", "ul_dashed": "\033[4:5m",
    "blink": "\033[5m", "strike": "\033[9m", "overline": "\033[53m", "reverse": "\033[7m",
}


def _build_ansi(entry: dict) -> str:
    """Build ANSI escape string from a theme config entry."""
    parts: list[str] = []
    for attr in entry.get("attrs", []):
        sgr = _ATTR_SGR.get(attr)
        if sgr:
            parts.append(sgr)
    fg = entry.get("fg")
    if fg is not None:
        parts.append(f"\033[38;5;{fg}m")
    bg = entry.get("bg")
    if bg is not None:
        parts.append(f"\033[48;5;{bg}m")
    return "".join(parts)


def _load_theme_config() -> list[dict]:
    """Load theme overrides from config file into T class. Return slots config."""
    global SEP2, SEP_DOT

    if not THEME_FILE.exists():
        return list(DEFAULT_SLOTS)
    try:
        config = json.loads(THEME_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return list(DEFAULT_SLOTS)
    for key, entry in config.items():
        if key == "slots":
            continue
        if hasattr(T, key) and key != "R":
            setattr(T, key, _build_ansi(entry))
    SEP2 = f" {T.sep}|{T.R} "
    SEP_DOT = f" {T.sep}·{T.R} "
    return config.get("slots", list(DEFAULT_SLOTS))


# --- helpers -----------------------------------------------------------------

def run(cmd: list[str], *, cwd: str | None = None, timeout: float = TIMEOUT_SUBPROCESS) -> str | None:
    """Run a subprocess, return stdout or None on any failure."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
        if r.returncode == 0:
            return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def osc8_link(url: str, text: str) -> str:
    """OSC 8 terminal hyperlink."""
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def is_cache_fresh(path: Path, ttl: int) -> bool:
    """Check if a cache file exists and is younger than *ttl* seconds."""
    try:
        age = time.time() - path.stat().st_mtime
        return age < ttl
    except OSError:
        return False


def read_remote_url(cwd: str) -> str | None:
    """Read origin remote URL from .git/config — no subprocess."""
    git_dir = Path(cwd) / ".git"
    try:
        if git_dir.is_file():
            # worktree: .git contains "gitdir: /path/to/actual/.git"
            text = git_dir.read_text().strip()
            if text.startswith("gitdir: "):
                git_dir = Path(text[8:])
                if not git_dir.is_absolute():
                    git_dir = (Path(cwd) / git_dir).resolve()
        config = (git_dir / "config").read_text()
    except OSError:
        return None

    in_origin = False
    for line in config.splitlines():
        s = line.strip()
        if s == '[remote "origin"]':
            in_origin = True
        elif s.startswith("["):
            in_origin = False
        elif in_origin and s.startswith("url = "):
            return s[6:]
    return None


# --- gh availability ---------------------------------------------------------

def check_gh_available() -> str:
    """Return 'ok', 'no-gh', or 'no-auth'. Result is cached on disk."""
    if GH_AVAILABLE_FILE.exists():
        try:
            age = time.time() - GH_AVAILABLE_FILE.stat().st_mtime
            if age < GH_CHECK_TTL:
                cached = GH_AVAILABLE_FILE.read_text().strip()
                if cached:
                    return cached
        except OSError:
            pass

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if shutil.which("gh") is None:
        GH_AVAILABLE_FILE.write_text("no-gh")
        return "no-gh"

    if run(["gh", "auth", "status"]) is None:
        GH_AVAILABLE_FILE.write_text("no-auth")
        return "no-auth"

    GH_AVAILABLE_FILE.write_text("ok")
    return "ok"


# --- directory name ----------------------------------------------------------

def get_dir_name(current_dir: str) -> str:
    """Return 'parent/current/' with parent truncated."""
    p = Path(current_dir)
    current = p.name or str(p)
    parent = p.parent.name
    if parent and parent != current:
        if len(parent) > PARENT_DIR_MAX_LEN:
            parent = parent[: PARENT_DIR_MAX_LEN - 1] + "…"
        return f"{T.dir_parent}{parent}/{T.R}{T.dir_name}{current}/{T.R}"
    return f"{T.dir_name}{current}/{T.R}"


# --- git info ----------------------------------------------------------------

def get_git_info(cwd: str) -> tuple[str, str]:
    """Return (branch, status_indicators). Both may be empty."""
    branch = ""
    indicators = ""

    # one call for branch + file statuses
    out = run(["git", "-C", cwd, "--no-optional-locks", "status", "--porcelain=v1", "--branch"], timeout=TIMEOUT_GIT)
    if out is None:
        return branch, indicators

    lines = out.split("\n")
    if not lines:
        return branch, indicators

    header = lines[0]  # ## branch...origin/branch [ahead N, behind M]

    # extract branch from header: "## main...origin/main [ahead 1]" or "## main"
    if header.startswith("## "):
        branch_part = header[3:]
        if "..." in branch_part:
            branch = branch_part.split("...")[0]
        elif " " in branch_part:
            branch = branch_part.split(" ")[0]
        else:
            branch = branch_part
        if branch in ("HEAD", "No"):  # detached HEAD or "No commits yet"
            branch = ""

    # parse ahead/behind
    ahead = ""
    behind = ""
    m = re.search(r"ahead (\d+)", header)
    if m:
        ahead = m.group(1)
    m = re.search(r"behind (\d+)", header)
    if m:
        behind = m.group(1)

    # parse file statuses (lines after header)
    dirty = staged = untracked = False
    for line in lines[1:]:
        if len(line) < 2:
            continue
        x, y = line[0], line[1]
        if x in "MADRC":
            staged = True
        if y in "MD":
            dirty = True
        if x == "?" and y == "?":
            untracked = True

    # build indicators
    parts: list[str] = []
    if dirty:
        parts.append(f"{T.git_dirty}*{T.R}")
    if staged:
        parts.append(f"{T.git_staged}+{T.R}")
    if untracked:
        parts.append(f"{T.git_untracked}?{T.R}")
    if ahead:
        parts.append(f"{T.git_ahead}↑{T.R}")
    if behind:
        parts.append(f"{T.git_behind}↓{T.R}")
    indicators = "".join(parts)

    return branch, indicators


# --- PR status ---------------------------------------------------------------

def _refresh_pr_cache_subprocess() -> None:
    """Fire-and-forget background refresh of PR cache."""
    # This runs as a detached subprocess so it doesn't block the statusline.
    script = r"""
import fcntl, json, os, subprocess, sys
from pathlib import Path

TIMEOUT_GH_API = """ + str(TIMEOUT_GH_API) + r"""
GH_PR_FETCH_LIMIT = """ + str(GH_PR_FETCH_LIMIT) + r"""

CACHE_DIR = Path(sys.argv[1])
LOCK = CACHE_DIR / "refresh.lock"
CACHE = CACHE_DIR / "pr-status.json"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

fd = os.open(str(LOCK), os.O_WRONLY | os.O_CREAT)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    os.close(fd)
    sys.exit(0)

try:
    # GraphQL: open PRs with CI status
    gql = subprocess.run(
        ["gh", "api", "graphql", "-f", "query=" + '''
        query {
            search(query: "is:open is:pr author:@me", type: ISSUE, first: ''' + str(GH_PR_FETCH_LIMIT) + ''') {
                nodes {
                    ... on PullRequest {
                        number
                        repository { nameWithOwner }
                        url
                        headRefName
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
        '''.strip()],
        capture_output=True, text=True, timeout=TIMEOUT_GH_API,
    )
    prs = json.loads(gql.stdout) if gql.returncode == 0 else {}

    # REST: unread notifications (participating)
    notif = subprocess.run(
        ["gh", "api", "notifications"], capture_output=True, text=True, timeout=TIMEOUT_GH_API,
    )
    unread = 0
    if notif.returncode == 0:
        participating_reasons = {"comment", "mention", "author", "review_requested", "assign"}
        for n in json.loads(notif.stdout):
            if (n.get("subject", {}).get("type") in ("PullRequest", "Issue")
                    and n.get("unread")
                    and n.get("reason") in participating_reasons):
                unread += 1

    result = {"prs": prs, "unread_count": unread, "updated_at": int(__import__('time').time())}

    tmp = str(CACHE) + f".tmp.{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(result, f)
    os.replace(tmp, str(CACHE))
finally:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
"""
    subprocess.Popen(
        [sys.executable, "-c", script, str(CACHE_DIR)],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def get_pr_status() -> str:
    """Return formatted PR dot string from cache, trigger refresh if stale."""
    gh = check_gh_available()
    if gh == "no-gh":
        return f"{T.err}gh not installed{T.R}"
    if gh == "no-auth":
        return f"{T.err}gh auth login{T.R}"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not is_cache_fresh(PR_CACHE_FILE, PR_CACHE_TTL):
        _refresh_pr_cache_subprocess()

    if not PR_CACHE_FILE.exists():
        return ""

    try:
        cache = json.loads(PR_CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return ""

    nodes = cache.get("prs", {}).get("data", {}).get("search", {}).get("nodes", [])
    if not nodes:
        return ""

    # sort dots by severity: red → blue → green → gray
    dots_red: list[str] = []
    dots_pending: list[str] = []
    dots_green: list[str] = []
    dots_gray: list[str] = []

    for pr in nodes:
        url = pr.get("url", "")
        commits = pr.get("commits", {}).get("nodes", [])
        state = "UNKNOWN"
        if commits:
            rollup = commits[0].get("commit", {}).get("statusCheckRollup")
            if rollup:
                state = rollup.get("state", "UNKNOWN")

        dot = osc8_link(url, PR_DOT) if url else PR_DOT
        if state in ("FAILURE", "ERROR"):
            dots_red.append(dot)
        elif state in ("PENDING", "EXPECTED"):
            dots_pending.append(dot)
        elif state == "SUCCESS":
            dots_green.append(dot)
        else:
            dots_gray.append(dot)

    parts: list[str] = []
    if dots_red:
        parts.append(f"{T.pr_fail}{''.join(dots_red)}{T.R}")
    if dots_pending:
        parts.append(f"{T.pr_wait}{''.join(dots_pending)}{T.R}")
    if dots_green:
        parts.append(f"{T.pr_ok}{''.join(dots_green)}{T.R}")
    if dots_gray:
        parts.append(f"{T.pr_none}{''.join(dots_gray)}{T.R}")

    output = "".join(parts)

    # unread notifications count
    unread = cache.get("unread_count", 0)
    if unread > 0:
        output += f" {T.notif}💬{unread}{T.R}"

    return output


# --- CI status (per-branch, separate from PR dots) ---------------------------

def _ci_from_pr_cache(branch: str) -> str | None:
    """Try to get CI status from PR cache if branch matches an open PR.

    Returns formatted label or None if branch not found in cache.
    """
    if not PR_CACHE_FILE.exists():
        return None
    try:
        cache = json.loads(PR_CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    for pr in cache.get("prs", {}).get("data", {}).get("search", {}).get("nodes", []):
        if pr.get("headRefName") != branch:
            continue
        commits = pr.get("commits", {}).get("nodes", [])
        if not commits:
            return _format_ci_label("pending")
        rollup = commits[0].get("commit", {}).get("statusCheckRollup")
        if not rollup:
            return _format_ci_label("pending")
        state = rollup.get("state", "UNKNOWN")
        mapping = {
            "SUCCESS": "success",
            "FAILURE": "failure",
            "ERROR": "failure",
            "PENDING": "pending",
            "EXPECTED": "pending",
        }
        return _format_ci_label(mapping.get(state, ""))
    return None


def _parse_owner_repo(remote_url: str) -> tuple[str, str] | None:
    """Parse owner/repo from SSH or HTTPS git remote URL."""
    m = re.search(r"[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
    return (m.group(1), m.group(2)) if m else None


def get_ci_status(cwd: str, branch: str) -> str:
    """Return CI status label for the current branch.

    Priority: PR cache (0 forks) → CI disk cache → gh API (1 fork).
    """
    if not branch:
        return ""

    # fast path: if branch has an open PR, use CI from PR cache (no subprocess)
    from_pr = _ci_from_pr_cache(branch)
    if from_pr is not None:
        return from_pr

    gh = check_gh_available()
    if gh != "ok":
        return ""

    # read remote URL from .git/config (file I/O, no subprocess)
    remote_url = read_remote_url(cwd)
    if not remote_url:
        return ""

    parsed = _parse_owner_repo(remote_url)
    if not parsed:
        return ""
    owner, repo = parsed

    CI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CI_CACHE_DIR / f"{owner}_{repo}_{branch}.json"

    # return from disk cache if fresh
    if is_cache_fresh(cache_file, CI_CACHE_TTL):
        try:
            data = json.loads(cache_file.read_text())
            return _format_ci_label(data.get("conclusion"))
        except (json.JSONDecodeError, OSError):
            pass

    # fetch check-runs for branch HEAD (1 fork, only if all caches miss)
    out = run(
        ["gh", "api", f"repos/{owner}/{repo}/commits/{branch}/check-runs",
         "--jq", ".check_runs"],
        timeout=TIMEOUT_GH_API,
    )
    if out is None:
        return ""

    try:
        runs = json.loads(out)
    except json.JSONDecodeError:
        return ""

    if not runs:
        try:
            cache_file.write_text(json.dumps({"conclusion": None}))
        except OSError:
            pass
        return ""

    # aggregate: any failure → failure; all success → success; else pending
    conclusions = [r.get("conclusion") for r in runs]
    statuses = [r.get("status") for r in runs]

    if any(c in ("failure", "timed_out", "cancelled", "action_required") for c in conclusions):
        result = "failure"
    elif all(c == "success" for c in conclusions if c is not None) and all(s == "completed" for s in statuses):
        result = "success"
    elif any(s in ("queued", "in_progress") for s in statuses):
        result = "pending"
    else:
        result = "unknown"

    try:
        cache_file.write_text(json.dumps({"conclusion": result}))
    except OSError:
        pass

    return _format_ci_label(result)


def _format_ci_label(conclusion: str | None) -> str:
    """Format CI conclusion as a colored 'CI' label (color conveys status)."""
    if conclusion is None:
        return ""
    labels = {
        "success": f"{T.ci_ok}CI{T.R}",
        "failure": f"{T.ci_fail}CI{T.R}",
        "pending": f"{T.ci_wait}CI{T.R}",
    }
    return labels.get(conclusion, "")


# --- limits provider ---------------------------------------------------------

def _read_oauth_token() -> str | None:
    """Read OAuth access token from Claude credentials file."""
    try:
        data = json.loads(LIMITS_CREDS_FILE.read_text())
        return data["claudeAiOauth"]["accessToken"]
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def _parse_iso_utc(raw: str) -> float | None:
    """Parse ISO-8601 timestamp to epoch seconds (stdlib only)."""
    from datetime import datetime, timezone
    try:
        # strip fractional seconds (e.g. .127928) before timezone
        s = re.sub(r'\.\d+', '', raw)
        # normalize timezone offset
        s = s.replace("+00:00", "+0000").replace("Z", "+0000")
        if "+" in s[10:]:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
        else:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _format_duration(minutes: int) -> str:
    """Format minutes into compact duration: 4h26m, 3d 2h, 23m, now."""
    if minutes <= 0:
        return "now"
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if hours < 24:
        return f"{hours}h{mins:02d}m" if mins else f"{hours}h"
    days = hours // 24
    rem_hours = hours % 24
    return f"{days}d {rem_hours}h" if rem_hours else f"{days}d"


def _ramp(t: float, endpoints: tuple[int, int]) -> str:
    """Interpolate between two 256-color RGB cube indices. t ∈ [0, 1].

    Decomposes both endpoints into (R, G, B) ∈ 0..5, lerps each channel,
    reconstructs the index. Works for any two colors in the 16–231 cube.
    """
    t = max(0.0, min(1.0, t))
    c_lo, c_hi = endpoints
    lr, lg, lb = (c_lo - 16) // 36, ((c_lo - 16) % 36) // 6, (c_lo - 16) % 6
    hr, hg, hb = (c_hi - 16) // 36, ((c_hi - 16) % 36) // 6, (c_hi - 16) % 6
    r = max(0, min(5, round(lr + t * (hr - lr))))
    g = max(0, min(5, round(lg + t * (hg - lg))))
    b = max(0, min(5, round(lb + t * (hb - lb))))
    return f"\033[38;5;{16 + 36 * r + 6 * g + b}m"


def _pace_delta_color(delta: float) -> str:
    """Pace delta color: log-scaled cyan (under budget) or orange (over budget)."""
    import math
    magnitude = min(abs(delta), PACE_COLOR_MAX_DELTA)
    t = math.log1p(magnitude) / math.log1p(PACE_COLOR_MAX_DELTA)
    return _ramp(t, RAMP_CYAN if delta < 0 else RAMP_ORANGE)


def _ramp_color(pct: float, lo: float = 0.0, hi: float = 100.0) -> str:
    """Two-phase cyan→orange color for a value in [lo, hi] range."""
    t = max(0.0, min(1.0, (pct - lo) / (hi - lo)))
    if t <= 0.5:
        return _ramp(t * 2, RAMP_CYAN)
    return _ramp((t - 0.5) * 2, RAMP_ORANGE)


def _bar(pct: float, width: int = LIMITS_BAR_WIDTH, *,
         color_range: tuple[float, float] = (0.0, 100.0)) -> str:
    """Progress bar on dark bg, colored by cyan→orange ramp.

    pct: fill level 0..100.  color_range: (lo, hi) for ramp mapping.
    """
    clamped = max(0.0, min(100.0, pct))
    total = round(clamped / 100 * width * 8)
    total = max(0, min(width * 8, total))
    full = total // 8
    frac = total % 8
    empty = width - full - (1 if frac else 0)
    color = _ramp_color(clamped, *color_range)
    filled = f"{T.lim_bar_bg}{color}{'█' * full}{_BAR_EIGHTHS[frac] if frac else ''}{T.R}"
    bg_empty = f"{T.lim_bar_bg}{' ' * empty}{T.R}" if empty else ""
    return f"{filled}{bg_empty}"


def _7d_pace_label(utilization: float, resets_at: str) -> str:
    """Return pace label for 7d window assuming 5-day (120h) working budget."""
    reset_epoch = _parse_iso_utc(resets_at)
    if reset_epoch is None:
        return ""
    hours_elapsed = max(0.0, (time.time() - (reset_epoch - LIMITS_WINDOW_SECONDS)) / 3600)
    expected = min(hours_elapsed / LIMITS_PACE_BUDGET_HOURS * 100.0, 100.0)
    if expected < LIMITS_PACE_MIN_EXPECTED:
        return ""
    delta = utilization - expected
    dc = _pace_delta_color(delta)
    label = next(name for threshold, name in PACE_SCALE if delta <= threshold)
    return f"{dc}{label} {abs(delta):.0f}%{T.R}"


def _format_limit_window(utilization: float, resets_at: str, label: str,
                         show_pace: bool = False) -> str:
    """Format one limit window: '5h ▋    '."""
    pct = max(0.0, min(100.0, utilization))
    bar = _bar(pct)

    # show reset countdown only when utilization >= 50%
    time_str = ""
    if pct >= LIMITS_COUNTDOWN_THRESHOLD:
        reset_epoch = _parse_iso_utc(resets_at)
        if reset_epoch is not None:
            remaining_min = max(0, int((reset_epoch - time.time()) / 60))
            time_str = f" {T.lim_time}{_format_duration(remaining_min)}{T.R}"

    pace_str = _7d_pace_label(utilization, resets_at) if show_pace else ""
    if pace_str:
        pace_str = f"{SEP_DOT}{pace_str}"
    return f"{T.dir_parent}{label}{T.R} {bar}{time_str}{pace_str}"


def _refresh_limits_cache_subprocess() -> None:
    """Fire-and-forget background refresh of limits cache."""
    token = _read_oauth_token()
    if not token:
        return

    script = r"""
import fcntl, json, os, sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

CACHE = Path(sys.argv[1])
LOCK = Path(sys.argv[2])
API_URL = sys.argv[3]
TOKEN = sys.argv[4]
TIMEOUT = """ + str(LIMITS_HTTP_TIMEOUT) + r"""

CACHE.parent.mkdir(parents=True, exist_ok=True)

fd = os.open(str(LOCK), os.O_WRONLY | os.O_CREAT)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    os.close(fd)
    sys.exit(0)

try:
    req = Request(API_URL)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("anthropic-beta", "oauth-2025-04-20")
    resp = urlopen(req, timeout=TIMEOUT)
    data = json.loads(resp.read())

    tmp = str(CACHE) + f".tmp.{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, str(CACHE))
except (URLError, OSError, json.JSONDecodeError, ValueError):
    pass
finally:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
"""
    subprocess.Popen(
        [sys.executable, "-c", script,
         str(LIMITS_CACHE_FILE), str(LIMITS_LOCK_FILE),
         LIMITS_API_URL, token],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def provider_limits(input_json: str, cwd: str) -> str:
    """Built-in provider: API usage limits (5h/7d windows) + context window."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # trigger background refresh if cache stale
    if not is_cache_fresh(LIMITS_CACHE_FILE, LIMITS_CACHE_TTL):
        _refresh_limits_cache_subprocess()

    parts: list[str] = []

    # read cached limits data
    if LIMITS_CACHE_FILE.exists():
        try:
            data = json.loads(LIMITS_CACHE_FILE.read_text())
            five = data.get("five_hour", {})
            seven = data.get("seven_day", {})

            u5 = five.get("utilization", 0)
            u7 = seven.get("utilization", 0)

            # hierarchical display
            if u7 >= 100:
                parts.append(_format_limit_window(u7, seven.get("resets_at", ""), "7d", show_pace=True))
            elif u5 >= 100:
                parts.append(_format_limit_window(u5, five.get("resets_at", ""), "5h"))
                parts.append(_format_limit_window(u7, seven.get("resets_at", ""), "7d", show_pace=True))
            else:
                parts.append(_format_limit_window(u5, five.get("resets_at", ""), "5h"))
                parts.append(_format_limit_window(u7, seven.get("resets_at", ""), "7d", show_pace=True))
        except (json.JSONDecodeError, OSError):
            pass

    # context window from stdin JSON (no API call)
    try:
        inp = json.loads(input_json)
        remaining = inp.get("context_window", {}).get("remaining_percentage")
        if remaining is not None:
            used = 100 - remaining
            parts.append(f"{T.dir_parent}ctx{T.R} {_bar(used, color_range=CTX_COLOR_RANGE)}")
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return SEP_DOT.join(parts)


# --- slot providers ----------------------------------------------------------

def provider_git(input_json: str, cwd: str) -> str:
    """Built-in provider: directory + git + CI + PR line."""
    dir_name = get_dir_name(cwd)

    with ThreadPoolExecutor(max_workers=2) as pool:
        git_future = pool.submit(get_git_info, cwd)
        pr_future = pool.submit(get_pr_status)

        try:
            branch, git_status = git_future.result()
        except Exception:
            branch, git_status = "", ""

        try:
            pr_status = pr_future.result()
        except Exception:
            pr_status = ""

    # CI depends on branch, runs after git
    ci_label = ""
    if branch:
        try:
            ci_label = get_ci_status(cwd, branch)
        except Exception:
            ci_label = ""

    # assemble line
    line = dir_name
    if branch:
        line += f" {T.branch_sign}{BRANCH_LABEL}{T.R}{T.branch_name}{branch}{T.R}"
        if git_status:
            line += git_status
    if ci_label:
        line += f" {ci_label}"
    if pr_status:
        line += f"{SEP2}{pr_status}"
    return line


PROVIDERS: dict[str, callable] = {
    "git": provider_git,
    "limits": provider_limits,
}


# --- external slot executor --------------------------------------------------

def _refresh_external_slot_subprocess(command: str, input_json: str,
                                      cache_file: Path, lock_file: Path) -> None:
    """Fire-and-forget background refresh of an external slot cache."""
    script = r"""
import fcntl, os, subprocess, sys
from pathlib import Path

COMMAND = sys.argv[1]
CACHE = Path(sys.argv[2])
LOCK = Path(sys.argv[3])
TIMEOUT = """ + str(SLOT_TIMEOUT) + r"""

CACHE.parent.mkdir(parents=True, exist_ok=True)

fd = os.open(str(LOCK), os.O_WRONLY | os.O_CREAT)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    os.close(fd)
    sys.exit(0)

try:
    input_data = sys.stdin.read()
    env = {**os.environ, "FORCE_COLOR": "1"}
    r = subprocess.run(
        COMMAND, shell=True, input=input_data,
        capture_output=True, text=True, timeout=TIMEOUT, env=env,
    )
    if r.returncode == 0 and r.stdout.strip():
        tmp = str(CACHE) + f".tmp.{os.getpid()}"
        with open(tmp, "w") as f:
            f.write(r.stdout.strip())
        os.replace(tmp, str(CACHE))
except subprocess.TimeoutExpired:
    pass
finally:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script, command, str(cache_file), str(lock_file)],
        start_new_session=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        proc.stdin.write(input_json.encode())
        proc.stdin.flush()
        proc.stdin.close()
    except (OSError, BrokenPipeError):
        pass


def run_external_slot(command: str, input_json: str, ttl: int) -> str:
    """Return external slot output from cache, trigger bg refresh if stale."""
    SLOT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    expanded = os.path.expanduser(command)
    cache_key = hashlib.md5(expanded.encode()).hexdigest()
    cache_file = SLOT_CACHE_DIR / cache_key
    lock_file = SLOT_CACHE_DIR / f"{cache_key}.lock"

    if not is_cache_fresh(cache_file, ttl):
        _refresh_external_slot_subprocess(expanded, input_json, cache_file, lock_file)

    try:
        return cache_file.read_text().strip()
    except OSError:
        return ""


# --- slot orchestrator -------------------------------------------------------

def execute_slots(slots: list[dict], input_json: str, cwd: str) -> list[str]:
    """Execute all slots in parallel, return ordered list of non-empty lines."""
    slots = [s for s in slots if s.get("enabled", True)]

    def _run_slot(slot: dict) -> str:
        provider = slot.get("provider")
        if provider:
            func = PROVIDERS.get(provider)
            if func:
                return func(input_json, cwd)
            return ""
        command = slot.get("command")
        if command:
            ttl = slot.get("ttl", SLOT_CACHE_TTL)
            return run_external_slot(command, input_json, ttl)
        return ""

    results = [""] * len(slots)
    with ThreadPoolExecutor(max_workers=max(len(slots), 1)) as pool:
        futures = {pool.submit(_run_slot, slot): i for i, slot in enumerate(slots)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = ""

    return [line for line in results if line]


# --- render ------------------------------------------------------------------

def render(lines: list[str]) -> str:
    """Join slot output lines."""
    return "\n".join(lines)


# --- demo --------------------------------------------------------------------

def demo() -> None:
    """Print demo scenarios for visual testing."""
    D = PR_DOT

    def git_line(branch: str, status: str = "", ci: str = "", pr: str = "") -> str:
        """Assemble a git-style line for demo display."""
        line = f"{T.dir_name}{DEMO_DIR_NAME}{T.R}"
        if branch:
            line += f" {T.branch_sign}{BRANCH_LABEL}{T.R}{T.branch_name}{branch}{T.R}"
            if status:
                line += status
        if ci:
            line += f" {ci}"
        if pr:
            line += f"{SEP2}{pr}"
        return line

    def limits_line(u5: float, r5: str, u7: float, r7: str, ctx: int) -> str:
        """Assemble a limits-style line for demo display."""
        parts: list[str] = []
        if u7 >= 100:
            parts.append(_format_limit_window(u7, r7, "7d", show_pace=True))
        else:
            parts.append(_format_limit_window(u5, r5, "5h"))
            parts.append(_format_limit_window(u7, r7, "7d", show_pace=True))
        parts.append(f"{T.dir_parent}ctx{T.R} {_bar(ctx, color_range=CTX_COLOR_RANGE)}")
        return SEP_DOT.join(parts)

    # demo reset times (relative to now for realistic display)
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    r5h = (now + timedelta(hours=4, minutes=26)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    r5h_low = (now + timedelta(minutes=23)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    r7d = (now + timedelta(days=4, hours=17)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    r7d_med = (now + timedelta(days=1, hours=5)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    r7d_crit = (now + timedelta(days=2, hours=4)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    gsd_line = f"⬆ /gsd:update {T.sep}│{T.R} Fixing auth bug {T.sep}│{T.R} █████░░░░░ 52%"

    print("=== Demo: limits green — both windows low ===")
    print(render([
        limits_line(12, r5h, 35, r7d, 24),
        git_line(DEMO_BRANCH_MAIN, f"{T.git_staged}+{T.R}", "",
                 f"{T.pr_ok}{D}{D}{D}{T.R}"),
    ]))

    print("=== Demo: limits yellow — 5h warn ===")
    print(render([
        limits_line(70, r5h, 45, r7d, 65),
        git_line(DEMO_BRANCH_FEATURE, f"{T.git_dirty}*{T.R}{T.git_staged}+{T.R}",
                 f"{T.ci_fail}CI{T.R}",
                 f"{T.pr_fail}{D}{T.R}{T.pr_wait}{D}{D}{T.R}{T.pr_ok}{D}{D}{T.R}{T.pr_none}{D}{T.R} {T.notif}💬2{T.R}"),
    ]))

    print("=== Demo: 5h exhausted (red), 7d for context ===")
    print(render([
        limits_line(100, r5h_low, 80, r7d_med, 80),
        git_line(DEMO_BRANCH_FEATURE, f"{T.git_dirty}*{T.R}",
                 f"{T.ci_wait}CI{T.R}",
                 f"{T.pr_wait}{D}{T.R}{T.pr_ok}{D}{D}{T.R}"),
    ]))

    print("=== Demo: 7d exhausted — only 7d shown ===")
    print(render([
        limits_line(100, r5h_low, 100, r7d_crit, 45),
        git_line(DEMO_BRANCH_DEV, f"{T.git_ahead}↑{T.R}"),
    ]))

    print("=== Demo: 3-line with GSD slot ===")
    print(render([
        limits_line(25, r5h, 18, r7d, 30),
        gsd_line,
        git_line(DEMO_BRANCH_FEATURE, f"{T.git_dirty}*{T.R}{T.git_staged}+{T.R}",
                 f"{T.ci_fail}CI{T.R}",
                 f"{T.pr_fail}{D}{T.R}{T.pr_wait}{D}{D}{T.R}{T.pr_ok}{D}{D}{T.R}{T.pr_none}{D}{T.R} {T.notif}💬3{T.R}"),
    ]))

    print("=== Demo: gh not installed ===")
    print(render([
        limits_line(5, r5h, 10, r7d, 8),
        git_line(DEMO_BRANCH_MAIN, "", "", f"{T.err}gh not installed{T.R}"),
    ]))


# --- main --------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--theme":
        editor = Path(__file__).parent / "theme-editor.py"
        os.execvp(sys.executable, [sys.executable, str(editor)])

    slots = _load_theme_config()

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
        return

    # read JSON from stdin (1s timeout, like bash `read -t 1`)
    def _stdin_timeout(signum, frame):
        raise TimeoutError
    old_handler = signal.signal(signal.SIGALRM, _stdin_timeout)
    try:
        signal.alarm(1)
        raw = sys.stdin.read()
        signal.alarm(0)
    except TimeoutError:
        print("FATAL: Timed out reading stdin", file=sys.stderr)
        sys.exit(1)
    except (OSError, IOError, BrokenPipeError) as e:
        signal.alarm(0)
        print(f"FATAL: Failed to read stdin: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        signal.signal(signal.SIGALRM, old_handler)

    if not raw.strip():
        print("FATAL: No JSON input received from stdin", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"FATAL: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    current_dir = data.get("workspace", {}).get("current_dir")
    if not current_dir:
        print("FATAL: Failed to extract current_dir from JSON", file=sys.stderr)
        sys.exit(1)

    lines = execute_slots(slots, raw, current_dir)
    print(render(lines))


if __name__ == "__main__":
    main()
