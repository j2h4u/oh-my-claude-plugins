#!/usr/bin/env python3
"""Claude Code statusline — dir, git, PR dots, ccusage.

Reads JSON from stdin (Claude Code statusline protocol), renders a two-line
status: ccusage on line 1, directory + git + PR status on line 2.

Git status indicators:
  *  dirty (unstaged changes)   — yellow dim
  +  staged changes             — green dim
  ?  untracked files            — gray
  ↑  ahead of remote            — cyan
  ↓  behind remote              — purple
"""

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
TIMEOUT_CCUSAGE = 30     # bun x ccusage (can be slow)

# GitHub API limits
GH_PR_FETCH_LIMIT = 20   # max PRs to fetch in GraphQL query

# ccusage config
CCUSAGE_REFRESH_INTERVAL = 60  # seconds

# Error message truncation
STDERR_MAX_LEN = 50      # max stderr length in error messages

# Paths
CACHE_DIR = Path("/tmp") / "omcc-statusline"
THEME_FILE = Path.home() / ".config" / "omcc-statusline" / "theme.json"
PR_CACHE_FILE = CACHE_DIR / "pr-status.json"
PR_LOCK_FILE = CACHE_DIR / "refresh.lock"
GH_AVAILABLE_FILE = CACHE_DIR / "gh-available"
CI_CACHE_DIR = CACHE_DIR / "ci"


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
    # reset shorthand
    R              = Pal.R


SEP2 = f" {T.sep}|{T.R} "


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


def _load_theme_config() -> None:
    """Load theme overrides from config file into T class."""
    global SEP2

    if not THEME_FILE.exists():
        return
    try:
        config = json.loads(THEME_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return
    for key, entry in config.items():
        if hasattr(T, key) and key != "R":
            setattr(T, key, _build_ansi(entry))
    SEP2 = f" {T.sep}|{T.R} "


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

CACHE_DIR = Path(sys.argv[1])
LOCK = CACHE_DIR / "refresh.lock"
CACHE = CACHE_DIR / "pr-status.json"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

fd = os.open(str(LOCK), os.O_WRONLY | os.O_CREAT)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
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


# --- ccusage -----------------------------------------------------------------

def get_ccusage(input_json: str) -> str:
    """Run ccusage statusline via bun, return its output."""
    if shutil.which("bun") is None:
        return f"{T.err}bun not found{T.R}"

    try:
        env = {**os.environ, "FORCE_COLOR": "1"}
        r = subprocess.run(
            ["bun", "x", "ccusage", "statusline",
             "--visual-burn-rate", "text", "--refresh-interval", str(CCUSAGE_REFRESH_INTERVAL)],
            input=input_json, capture_output=True, text=True, timeout=TIMEOUT_CCUSAGE,
            env=env,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        # Show stderr truncated if available for non-zero returncode
        stderr_hint = ""
        if r.stderr:
            stderr = r.stderr.strip()
            if len(stderr) <= STDERR_MAX_LEN:
                stderr_hint = f" ({stderr})"
            else:
                stderr_hint = f" ({stderr[:STDERR_MAX_LEN - 3]}…)"
        return f"{T.err}ccusage code {r.returncode}{stderr_hint}{T.R}"
    except subprocess.TimeoutExpired:
        return f"{T.err}ccusage timeout ({TIMEOUT_CCUSAGE}s){T.R}"
    except FileNotFoundError:
        return f"{T.err}bun not found{T.R}"
    except OSError as e:
        return f"{T.err}ccusage OS error{T.R}"


# --- render ------------------------------------------------------------------

def render(dir_name: str, branch: str, git_status: str, ci_label: str,
           pr_status: str, ccusage_line: str) -> str:
    """Render the two-line statusline."""
    # line 2: dir + git + CI + PR
    line2 = dir_name

    if branch:
        line2 += f" {T.branch_sign}{BRANCH_LABEL}{T.R}{T.branch_name}{branch}{T.R}"
        if git_status:
            line2 += git_status

    if ci_label:
        line2 += f" {ci_label}"

    if pr_status:
        line2 += f"{SEP2}{pr_status}"

    return f"{ccusage_line}\n{line2}"


# --- demo --------------------------------------------------------------------

def demo() -> None:
    """Print demo scenarios for visual testing."""
    D = PR_DOT

    print("=== Demo: all green ===")
    print(render(
        f"{T.dir_name}{DEMO_DIR_NAME}{T.R}",
        DEMO_BRANCH_MAIN,
        f"{T.git_staged}+{T.R}",
        "",
        f"{T.pr_ok}{D}{D}{D}{T.R}",
        f"🤖 Sonnet 4.5 {T.sep}|{T.R} 💰 $12.34 session",
    ))

    print("=== Demo: mixed CI + unread comments ===")
    print(render(
        f"{T.dir_name}{DEMO_DIR_NAME}{T.R}",
        DEMO_BRANCH_FEATURE,
        f"{T.git_dirty}*{T.R}{T.git_staged}+{T.R}",
        f"{T.ci_fail}CI{T.R}",
        f"{T.pr_fail}{D}{T.R}{T.pr_wait}{D}{D}{T.R}{T.pr_ok}{D}{D}{T.R}{T.pr_none}{D}{T.R} {T.notif}💬3{T.R}",
        f"🤖 Opus 4.6 {T.sep}|{T.R} 💰 $58.07 session",
    ))

    print("=== Demo: gh not installed ===")
    print(render(
        f"{T.dir_name}{DEMO_DIR_NAME}{T.R}",
        DEMO_BRANCH_MAIN,
        "",
        "",
        f"{T.err}gh not installed{T.R}",
        f"🤖 Sonnet 4.5 {T.sep}|{T.R} 💰 $0.42 session",
    ))

    print("=== Demo: bun not found ===")
    print(render(
        f"{T.dir_name}{DEMO_DIR_NAME}{T.R}",
        DEMO_BRANCH_DEV,
        f"{T.git_ahead}↑{T.R}",
        "",
        "",
        f"{T.err}bun not found{T.R}",
    ))


# --- main --------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--theme":
        editor = Path(__file__).parent / "theme-editor.py"
        os.execvp(sys.executable, [sys.executable, str(editor)])

    _load_theme_config()

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

    # directory name — pure string, no subprocess
    dir_name = get_dir_name(current_dir)

    # parallel execution of 4 independent data sources
    results: dict[str, object] = {}

    def _git():
        return get_git_info(current_dir)

    def _pr():
        return get_pr_status()

    def _ccusage():
        return get_ccusage(raw)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_git): "git",
            pool.submit(_pr): "pr",
            pool.submit(_ccusage): "ccusage",
        }

        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception:
                results[key] = ("", "") if key == "git" else ""

    branch, git_status = results.get("git", ("", ""))
    pr_status = results.get("pr", "")
    ccusage_line = results.get("ccusage", "")

    # CI status depends on git branch, so it runs after git_info
    ci_label = ""
    if branch:
        try:
            ci_label = get_ci_status(current_dir, branch)
        except Exception:
            ci_label = ""

    print(render(dir_name, branch, git_status, ci_label, pr_status, ccusage_line))


if __name__ == "__main__":
    main()
