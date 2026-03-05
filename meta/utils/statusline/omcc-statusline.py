#!/usr/bin/env python3
"""Claude Code statusline + TUI theme editor — unified single file.

Statusline mode (default): Reads JSON from stdin (Claude Code statusline protocol),
renders N lines via a slot system. Each slot is either a built-in provider
(limits, git) or an external shell command.

Theme editor mode (--theme flag or symlinked as *theme*):
TUI for editing theme colors, attributes, and settings.

Config: ~/.config/omcc-statusline/config.json

Git status indicators:
  *  dirty (unstaged changes)   — yellow dim
  +  staged changes             — green dim
  ?  untracked files            — gray
  ↑  ahead of remote            — cyan
  ↓  behind remote              — purple
"""

import hashlib
import json
import math
import os
import re
import select
import shutil
import signal
import sys
import subprocess
import tempfile
import termios
import time
import tty
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

# --- constants ---------------------------------------------------------------

# Display
PARENT_DIR_MAX_LEN = 15
BRANCH_LABEL = "⑂"
PR_DOT = "⁕"

# Demo/example data
DEMO_DIR_NAME = "my-project/"
DEMO_BRANCH = "feature/wonderful-new-feature"
DEMO_BRANCH_MAIN = DEMO_BRANCH
DEMO_BRANCH_FEATURE = "feat/auth"
DEMO_BRANCH_DEV = "develop"
DEMO_PARENT_DIR = "workspace/"
DEMO_CURRENT_DIR = "my-project/"

# Paths
CONFIG_DIR = Path.home() / ".config" / "omcc-statusline"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path("/tmp") / "omcc-statusline"
PR_CACHE_FILE = CACHE_DIR / "pr-status.json"
PR_LOCK_FILE = CACHE_DIR / "refresh.lock"
GH_AVAILABLE_FILE = CACHE_DIR / "gh-available"
CI_CACHE_DIR = CACHE_DIR / "ci"
SLOT_CACHE_DIR = CACHE_DIR / "slots"

# Cache TTLs (seconds)
API_CACHE_TTL = 120      # 2 min — CI, PR, limits (anything that hits an API)
GH_CHECK_TTL = 1800      # 30 min — gh CLI availability (rarely changes)

# Timeouts (seconds)
TIMEOUT_SUBPROCESS = 5
TIMEOUT_GIT = 3
TIMEOUT_GH_API = 15
GH_PR_FETCH_LIMIT = 20

# Error/slot
STDERR_MAX_LEN = 50
SLOT_TIMEOUT = 120
SLOT_CACHE_TTL = 60

# Limits provider
LIMITS_CACHE_FILE = CACHE_DIR / "limits-cache.json"
LIMITS_LOCK_FILE = CACHE_DIR / "limits-refresh.lock"
LIMITS_CACHE_TTL = API_CACHE_TTL
LIMITS_HTTP_TIMEOUT = 5
LIMITS_API_URL = "https://api.anthropic.com/api/oauth/usage"
LIMITS_CREDS_FILE = Path.home() / ".claude" / ".credentials.json"
LIMITS_BAR_WIDTH = 5
LIMITS_WINDOW_SECONDS = 7 * 24 * 3600
LIMITS_PACE_BUDGET_HOURS = 120
LIMITS_COUNTDOWN_THRESHOLD = 50
LIMITS_PACE_MIN_EXPECTED = 1

PACE_SCALE = [
    (-20, "based"),
    ( -5, "hyped"),
    (  5, "chill"),
    ( 20, "salty"),
    (float("inf"), "depresso"),
]

RAMP_CYAN   = (23, 51)
RAMP_ORANGE = (58, 202)
PACE_COLOR_MAX_DELTA = 40

RAMP_PRESETS = {
    "aurora":    [(0, 44), (35, 33), (70, 127), (100, 160)],
    "traffic":   [(0, 35), (50, 185), (100, 160)],
    "twilight":  [(0, 33), (50, 92), (100, 124)],
    "ember":     [(0, 37), (50, 143), (100, 131)],
    "spectrum":  [(0, 35), (25, 44), (50, 33), (75, 127), (100, 160)],
    "heatmap":   [(0, 33), (25, 44), (50, 40), (75, 184), (100, 160)],
}

# INDICATOR_CONFIG — built from SETTINGS_DEFS after it's defined (see below)

_BAR_EIGHTHS = " ▏▎▍▌▋▊▉█"
_VBAR_EIGHTHS = " ▁▂▃▄▅▆▇█"

DEFAULT_SLOTS = [[{"provider": "path"}, {"provider": "git"}, {"provider": "limits"}, {"provider": "vibes"}]]

# --- ANSI helpers ------------------------------------------------------------

ESC = "\033"
CSI = f"{ESC}["

def fg256(n: int) -> str: return f"{CSI}38;5;{n}m"
def bg256(n: int) -> str: return f"{CSI}48;5;{n}m"
def ul_color(n: int) -> str: return f"{CSI}58;5;{n}m"

RESET         = f"{CSI}0m"
BOLD          = f"{CSI}1m"
DIM           = f"{CSI}2m"
ITALIC        = f"{CSI}3m"
UNDERLINE     = f"{CSI}4m"
UL_DOUBLE     = f"{CSI}21m"
UL_CURLY      = f"{CSI}4:3m"
UL_DOTTED     = f"{CSI}4:4m"
UL_DASHED     = f"{CSI}4:5m"
REVERSE       = f"{CSI}7m"
BLINK         = f"{CSI}5m"
STRIKE        = f"{CSI}9m"
OVERLINE      = f"{CSI}53m"

HIDE_CURSOR   = f"{CSI}?25l"
SHOW_CURSOR   = f"{CSI}?25h"
CLEAR_SCREEN  = f"{CSI}2J{CSI}H"
CLEAR_LINE    = f"{CSI}2K"


class T:
    """Semantic theme tokens — the only colors render code should reference."""
    dir_parent     = fg256(239)
    dir_name       = fg256(243)
    branch_sign    = fg256(66)
    branch_name    = fg256(66)
    git_dirty      = DIM + fg256(3)
    git_staged     = DIM + fg256(2)
    git_untracked  = fg256(3)
    git_ahead      = fg256(6)
    git_behind     = fg256(5)
    st_ok          = fg256(22)
    st_fail        = fg256(88)
    st_wait        = fg256(27)
    st_none        = fg256(8)
    notif          = fg256(6)
    sep            = fg256(241)
    err            = fg256(88)
    lim_time       = fg256(239)
    lim_bar_bg     = bg256(236)
    R              = RESET


ATTRS_AVAILABLE = [
    ("none",       "",        "Clear all attributes"),
    ("dim",        DIM,       "Dim/faint text"),
    ("bold",       BOLD,      "Bold text"),
    ("italic",     ITALIC,    "Italic text"),
    ("underline",  UNDERLINE, "Single underline"),
    ("ul_double",  UL_DOUBLE, "Double underline"),
    ("ul_curly",   UL_CURLY,  "Curly underline"),
    ("ul_dotted",  UL_DOTTED, "Dotted underline"),
    ("ul_dashed",  UL_DASHED, "Dashed underline"),
    ("blink",      BLINK,     "Blinking text"),
    ("strike",     STRIKE,    "Strikethrough"),
    ("overline",   OVERLINE,  "Overline"),
    ("reverse",    REVERSE,   "Swap FG/BG"),
]

ATTR_SGR = {name: sgr for name, sgr, _ in ATTRS_AVAILABLE}

# SEP_GIT, SEP_LIMITS, SEP_EXTRA — built from SETTINGS_DEFS below

# --- theme editor data model ------------------------------------------------

_ALL_PROPS = frozenset({"fg", "bg", "attrs"})


@dataclass
class ElementDef:
    key: str
    label: str
    desc: str
    sample: str
    group: str
    props: frozenset[str] = field(default_factory=lambda: _ALL_PROPS)
    gap: str = ""  # preview gap before element: "" | " " | "  " | "sep" | "git_sep"


ELEMENTS = [
    ElementDef("dir_parent",    "Parent dir",     "Muted parent directory in path",     DEMO_PARENT_DIR,   "dir"),
    ElementDef("dir_name",      "Current dir",    "Current working directory name",     DEMO_CURRENT_DIR,  "dir"),
    ElementDef("sep",           "Separator",      "Section separator",                  "|",        "ui"),
    ElementDef("branch_sign",   "Branch sign",    "Git branch indicator symbol",        "⑂",               "git"),
    ElementDef("branch_name",   "Branch name",    "Current git branch name",            DEMO_BRANCH,       "git"),
    ElementDef("git_dirty",     "Dirty",          "Unstaged changes indicator",         "*",        "git"),
    ElementDef("git_staged",    "Staged",         "Staged changes indicator",           "+",        "git"),
    ElementDef("git_untracked", "Untracked",      "Untracked files indicator",          "?",        "git"),
    ElementDef("git_ahead",     "Ahead",          "Commits ahead of remote",            "↑",        "git"),
    ElementDef("git_behind",    "Behind",         "Commits behind remote",              "↓",        "git"),
    ElementDef("st_ok",         "Status OK",      "CI pass / PR dot green",             "CI",       "ci",  gap="git_sep"),
    ElementDef("st_fail",       "Status fail",    "CI fail / PR dot red",               "CI",       "ci",  gap=" "),
    ElementDef("st_wait",       "Status wait",    "CI pending / PR dot blue",           "CI",       "ci",  gap=" "),
    ElementDef("st_none",       "Status none",    "CI/PR not configured (dim)",         "CI",       "ci",  gap=" "),
    ElementDef("notif",         "Notifications",  "Unread notification count",          "💬3",      "pr",  gap=" "),
    ElementDef("err",           "Error",          "Error messages",                     "error",    "ui",  gap="  "),
    ElementDef("lim_time",      "Lim time",       "Reset countdown",                    "4h26m",    "lim", gap="sep"),
    ElementDef("lim_bar_bg",    "Bar bg",         "Progress bar background (fg = ramp)", "▁▂▃",      "lim", frozenset({"bg"})),
]

# Runtime check: T theme tokens must match ELEMENTS definitions
_element_keys = frozenset(e.key for e in ELEMENTS)


@dataclass
class ThemeEntry:
    fg: int | None = None
    bg: int | None = None
    attrs: list[str] = field(default_factory=list)

    def copy(self) -> "ThemeEntry":
        return ThemeEntry(fg=self.fg, bg=self.bg, attrs=list(self.attrs))


DEFAULTS: dict[str, ThemeEntry] = {
    "dir_parent":     ThemeEntry(fg=239),
    "dir_name":       ThemeEntry(fg=243),
    "branch_sign":    ThemeEntry(fg=66),
    "branch_name":    ThemeEntry(fg=66),
    "git_dirty":      ThemeEntry(fg=3, attrs=["dim"]),
    "git_staged":     ThemeEntry(fg=2, attrs=["dim"]),
    "git_untracked":  ThemeEntry(fg=3),
    "git_ahead":      ThemeEntry(fg=6),
    "git_behind":     ThemeEntry(fg=5),
    "st_ok":          ThemeEntry(fg=22),
    "st_fail":        ThemeEntry(fg=88),
    "st_wait":        ThemeEntry(fg=27),
    "st_none":        ThemeEntry(fg=8),
    "notif":          ThemeEntry(fg=6),
    "sep":            ThemeEntry(fg=241),
    "err":            ThemeEntry(fg=88),
    "lim_time":       ThemeEntry(fg=239),
    "lim_bar_bg":     ThemeEntry(bg=236),
}

assert frozenset(DEFAULTS.keys()) == _element_keys, "DEFAULTS and ELEMENTS out of sync"
del _element_keys

# Build T from DEFAULTS (single source of truth for colors)
for _k, _d in DEFAULTS.items():
    _parts = [ATTR_SGR[a] for a in _d.attrs if a in ATTR_SGR]
    if _d.fg is not None:
        _parts.append(fg256(_d.fg))
    if _d.bg is not None:
        _parts.append(bg256(_d.bg))
    setattr(T, _k, "".join(_parts))
del _k, _d, _parts

RAMP_NAMES = ["aurora", "traffic", "twilight", "ember", "spectrum", "heatmap"]
DISPLAY_MODES = ["number", "vertical", "horizontal"]
SEP_OPTIONS = ["·", "•", "│", "─", "⋮", "|", "║", "┃", "❘", ""]
_SEP_DISPLAY = {"": "∅"}


@dataclass
class SettingDef:
    key: str
    label: str
    options: list[str]
    default: str


SETTINGS_DEFS = [
    SettingDef("5h_ramp",           "5h ramp",          RAMP_NAMES,          "spectrum"),
    SettingDef("7d_ramp",           "7d ramp",          RAMP_NAMES,          "spectrum"),
    SettingDef("ctx_ramp",          "ctx ramp",         RAMP_NAMES,          "aurora"),
    SettingDef("5h_display",        "5h display",       DISPLAY_MODES,       "vertical"),
    SettingDef("7d_display",        "7d display",       DISPLAY_MODES,       "vertical"),
    SettingDef("ctx_display",       "ctx display",      DISPLAY_MODES,       "vertical"),
    SettingDef("separator",         "Sep providers",    SEP_OPTIONS, "⋮"),
    SettingDef("git_separator",     "Sep git",          SEP_OPTIONS, "·"),
    SettingDef("limits_separator",  "Sep limits",       SEP_OPTIONS, ""),
]

# Build SEP_* from SETTINGS_DEFS (single source of truth for separators)
_SETTINGS_DEFAULTS = {s.key: s.default for s in SETTINGS_DEFS}

def _sep_ansi(char: str) -> str:
    """Build separator ANSI string: ' sep_colorCHARreset ' or just ' '."""
    return f" {T.sep}{char}{T.R} " if char else " "

SEP_EXTRA = _sep_ansi(_SETTINGS_DEFAULTS["separator"])
SEP_GIT = _sep_ansi(_SETTINGS_DEFAULTS["git_separator"])
SEP_LIMITS = _sep_ansi(_SETTINGS_DEFAULTS["limits_separator"])

# Build INDICATOR_CONFIG from SETTINGS_DEFS (single source of truth for ramp/display)
INDICATOR_CONFIG = {
    prefix: {
        "ramp": RAMP_PRESETS[_SETTINGS_DEFAULTS[f"{prefix}_ramp"]],
        "display": _SETTINGS_DEFAULTS[f"{prefix}_display"],
    }
    for prefix in ("5h", "7d", "ctx")
}

# --- config validation -------------------------------------------------------

_VALID_THEME_TOKENS = frozenset(e.key for e in ELEMENTS)
_VALID_SETTINGS_KEYS = frozenset(s.key for s in SETTINGS_DEFS)
_VALID_TOP_KEYS = frozenset({"slots", "settings", "theme"})
_VALID_SLOT_KEYS = frozenset({"provider", "command", "ttl", "enabled", "show"})
_VALID_ATTRS = frozenset(name for name, _, _ in ATTRS_AVAILABLE)


def _validate_config(config: dict) -> list[str]:
    """Validate hierarchical config, return list of error strings."""
    errors: list[str] = []

    for key in config:
        if key not in _VALID_TOP_KEYS:
            hint = ' (theme tokens go inside "theme")' if key in _VALID_THEME_TOKENS else ""
            errors.append(f"unknown top-level key: '{key}'{hint}")

    theme = config.get("theme")
    if theme is not None:
        if not isinstance(theme, dict):
            errors.append("theme: must be an object")
        else:
            for token, val in theme.items():
                if token not in _VALID_THEME_TOKENS:
                    errors.append(f"theme: unknown token '{token}'")
                    continue
                if not isinstance(val, dict):
                    errors.append(f"theme.{token}: must be an object")
                    continue
                for fld in val:
                    if fld not in ("fg", "bg", "attrs"):
                        errors.append(f"theme.{token}: unknown field '{fld}'")
                fg = val.get("fg")
                if fg is not None and (not isinstance(fg, int) or not 0 <= fg <= 255):
                    errors.append(f"theme.{token}.fg: must be 0-255, got {fg!r}")
                bg = val.get("bg")
                if bg is not None and (not isinstance(bg, int) or not 0 <= bg <= 255):
                    errors.append(f"theme.{token}.bg: must be 0-255, got {bg!r}")
                attrs = val.get("attrs")
                if attrs is not None:
                    if not isinstance(attrs, list):
                        errors.append(f"theme.{token}.attrs: must be a list")
                    else:
                        for a in attrs:
                            if a not in _VALID_ATTRS:
                                errors.append(f"theme.{token}.attrs: unknown attr '{a}'")

    settings = config.get("settings")
    if settings is not None:
        if not isinstance(settings, dict):
            errors.append("settings: must be an object")
        else:
            ramp_names = set(RAMP_PRESETS.keys())
            display_modes = set(DISPLAY_MODES)
            for key, val in settings.items():
                if key not in _VALID_SETTINGS_KEYS:
                    errors.append(f"settings: unknown key '{key}'")
                elif key in ("5h_ramp", "7d_ramp", "ctx_ramp"):
                    if val not in ramp_names:
                        errors.append(
                            f"settings.{key}: must be one of "
                            f"[{', '.join(sorted(ramp_names))}], got {val!r}"
                        )
                elif key in ("5h_display", "7d_display", "ctx_display"):
                    if val not in display_modes:
                        errors.append(
                            f"settings.{key}: must be one of "
                            f"[number, vertical, horizontal], got {val!r}"
                        )
                elif key in ("separator", "git_separator", "limits_separator"):
                    if not isinstance(val, str):
                        errors.append(f"settings.{key}: must be a string")

    slots = config.get("slots")
    if slots is not None:
        if not isinstance(slots, list):
            errors.append("slots: must be an array")
        else:
            provider_names = set(PROVIDERS.keys())
            for i, item in enumerate(slots):
                items = item if isinstance(item, list) else [item]
                for j, slot in enumerate(items):
                    prefix = f"slots[{i}][{j}]" if isinstance(item, list) else f"slots[{i}]"
                    if not isinstance(slot, dict):
                        errors.append(f"{prefix}: must be an object")
                        continue
                    for fld in slot:
                        if fld not in _VALID_SLOT_KEYS:
                            errors.append(f"{prefix}: unknown field '{fld}'")
                    has_provider = "provider" in slot
                    has_command = "command" in slot
                    if not has_provider and not has_command:
                        errors.append(f"{prefix}: must have 'provider' or 'command'")
                    elif has_provider and has_command:
                        errors.append(f"{prefix}: cannot have both 'provider' and 'command'")
                    if has_provider and slot["provider"] not in provider_names:
                        errors.append(
                            f"{prefix}: unknown provider '{slot['provider']}', "
                            f"valid: [{', '.join(sorted(provider_names))}]"
                        )
                    if has_command and not isinstance(slot["command"], str):
                        errors.append(f"{prefix}.command: must be a string")
                    ttl = slot.get("ttl")
                    if ttl is not None and not isinstance(ttl, (int, float)):
                        errors.append(f"{prefix}.ttl: must be a number")
                    enabled = slot.get("enabled")
                    if enabled is not None and not isinstance(enabled, bool):
                        errors.append(f"{prefix}.enabled: must be a boolean")
                    show = slot.get("show")
                    if show is not None:
                        if not isinstance(show, list):
                            errors.append(f"{prefix}.show: must be an array")
                        elif has_provider:
                            prov = slot["provider"]
                            valid_sections = PROVIDER_SECTIONS.get(prov)
                            if valid_sections is None:
                                errors.append(
                                    f"{prefix}.show: provider '{prov}' has no sections"
                                )
                            else:
                                for s in show:
                                    if not isinstance(s, str):
                                        errors.append(f"{prefix}.show: values must be strings")
                                    elif s not in valid_sections:
                                        errors.append(
                                            f"{prefix}.show: unknown section '{s}', "
                                            f"valid: [{', '.join(valid_sections)}]"
                                        )

    return errors


# --- config loading ----------------------------------------------------------

def _build_ansi(entry: dict) -> str:
    """Build ANSI escape string from a theme config entry dict."""
    parts: list[str] = []
    for attr in entry.get("attrs", []):
        sgr = ATTR_SGR.get(attr)
        if sgr:
            parts.append(sgr)
    fg = entry.get("fg")
    if fg is not None:
        parts.append(fg256(fg))
    bg = entry.get("bg")
    if bg is not None:
        parts.append(bg256(bg))
    return "".join(parts)


def build_style(entry: "ThemeEntry", extra: str = "") -> str:
    """Build ANSI escape string from a ThemeEntry (delegates to _build_ansi)."""
    d: dict = {}
    if entry.attrs:
        d["attrs"] = entry.attrs
    if entry.fg is not None:
        d["fg"] = entry.fg
    if entry.bg is not None:
        d["bg"] = entry.bg
    result = _build_ansi(d)
    if extra:
        result += extra
    return result


def _load_theme_config() -> list[dict]:
    """Load theme overrides from config file into T class. Return slots config."""
    global SEP_GIT, SEP_LIMITS, SEP_EXTRA

    if not CONFIG_FILE.exists():
        return list(DEFAULT_SLOTS)
    try:
        config = json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"config: failed to parse JSON: {exc}", file=sys.stderr)
        print(f"Fix: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    errors = _validate_config(config)
    if errors:
        for e in errors:
            print(f"config: {e}", file=sys.stderr)
        print(f"Fix: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    # apply theme token overrides
    theme = config.get("theme", {})
    for key, entry in theme.items():
        if isinstance(entry, dict) and hasattr(T, key):
            setattr(T, key, _build_ansi(entry))

    # read settings
    settings = config.get("settings", {})

    for prefix in ("5h", "7d", "ctx"):
        name = settings.get(f"{prefix}_ramp")
        if name and name in RAMP_PRESETS:
            INDICATOR_CONFIG[prefix]["ramp"] = RAMP_PRESETS[name]
        mode = settings.get(f"{prefix}_display")
        if mode in ("number", "vertical", "horizontal"):
            INDICATOR_CONFIG[prefix]["display"] = mode

    sep_char = settings.get("separator")
    if isinstance(sep_char, str):
        SEP_EXTRA = _sep_ansi(sep_char)
    else:
        SEP_EXTRA = _sep_ansi(_SETTINGS_DEFAULTS["separator"])

    git_sep = settings.get("git_separator")
    if isinstance(git_sep, str):
        SEP_GIT = _sep_ansi(git_sep)
    else:
        SEP_GIT = _sep_ansi(_SETTINGS_DEFAULTS["git_separator"])

    lim_sep = settings.get("limits_separator")
    if isinstance(lim_sep, str):
        SEP_LIMITS = _sep_ansi(lim_sep)
    else:
        SEP_LIMITS = _sep_ansi(_SETTINGS_DEFAULTS["limits_separator"])

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


def _read_json(path: Path) -> dict | None:
    """Read and parse a JSON cache file, return None on any error."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _cached_json(path: Path, ttl: int, refresh: "callable") -> dict | None:
    """Return parsed JSON from cache, trigger background refresh if stale."""
    if not is_cache_fresh(path, ttl):
        refresh()
    return _read_json(path)


def read_remote_url(cwd: str) -> str | None:
    """Read origin remote URL from .git/config — no subprocess."""
    git_dir = Path(cwd) / ".git"
    try:
        if git_dir.is_file():
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


# --- color ramp --------------------------------------------------------------

def _rgb_cube(r: int, g: int, b: int) -> int:
    """Convert RGB cube coords (0-5 each) to 256-color index."""
    return 16 + 36 * r + 6 * g + b


def _ramp_lerp(t: float, c_lo: int, c_hi: int) -> int:
    """Interpolate between two 256-color RGB cube indices. Returns color index."""
    t = max(0.0, min(1.0, t))
    lr, lg, lb = (c_lo - 16) // 36, ((c_lo - 16) % 36) // 6, (c_lo - 16) % 6
    hr, hg, hb = (c_hi - 16) // 36, ((c_hi - 16) % 36) // 6, (c_hi - 16) % 6
    r = max(0, min(5, round(lr + t * (hr - lr))))
    g = max(0, min(5, round(lg + t * (hg - lg))))
    b = max(0, min(5, round(lb + t * (hb - lb))))
    return _rgb_cube(r, g, b)


def _ramp(t: float, endpoints: tuple[int, int]) -> str:
    """Interpolate between two 256-color indices, return ANSI fg escape."""
    return fg256(_ramp_lerp(t, *endpoints))


def _multi_ramp_color(pct: float, waypoints: list[tuple[float, int]]) -> int:
    """Piecewise-linear color ramp across multiple waypoints, returns color index."""
    if pct <= waypoints[0][0]:
        return waypoints[0][1]
    if pct >= waypoints[-1][0]:
        return waypoints[-1][1]
    for i in range(len(waypoints) - 1):
        p0, c0 = waypoints[i]
        p1, c1 = waypoints[i + 1]
        if pct <= p1:
            t = (pct - p0) / (p1 - p0) if p1 > p0 else 0.0
            return _ramp_lerp(t, c0, c1)
    return waypoints[-1][1]


def _multi_ramp(pct: float, waypoints: list[tuple[float, int]]) -> str:
    """Piecewise-linear color ramp, returns ANSI fg escape."""
    return fg256(_multi_ramp_color(pct, waypoints))


def _pace_delta_color(delta: float) -> str:
    """Pace delta color: log-scaled cyan (under budget) or orange (over budget)."""
    magnitude = min(abs(delta), PACE_COLOR_MAX_DELTA)
    t = math.log1p(magnitude) / math.log1p(PACE_COLOR_MAX_DELTA)
    return _ramp(t, RAMP_CYAN if delta < 0 else RAMP_ORANGE)


# --- bar rendering -----------------------------------------------------------

def _resolve_bar_bg(bar_bg: str | None) -> str:
    """Return explicit bar_bg or fall back to T.lim_bar_bg."""
    return bar_bg if bar_bg is not None else T.lim_bar_bg


def _bar(pct: float, width: int = LIMITS_BAR_WIDTH, *, ramp: list, bar_bg: str | None = None) -> str:
    """Progress bar on dark bg, colored by ramp. bar_bg defaults to T.lim_bar_bg."""
    bg = _resolve_bar_bg(bar_bg)
    clamped = max(0.0, min(100.0, pct))
    total = round(clamped / 100 * width * 8)
    total = max(1 if clamped > 0 else 0, min(width * 8, total))
    full = total // 8
    frac = total % 8
    empty = width - full - (1 if frac else 0)
    color = _multi_ramp(clamped, ramp)
    filled = f"{bg}{color}{'█' * full}{_BAR_EIGHTHS[frac] if frac else ''}{T.R}"
    bg_empty = f"{bg}{' ' * empty}{T.R}" if empty else ""
    return f"{filled}{bg_empty}"


def _vbar(pct: float, *, ramp: list, bar_bg: str | None = None) -> str:
    """Single-character vertical progress bar (bottom→up), colored."""
    bg = _resolve_bar_bg(bar_bg)
    clamped = max(0.0, min(100.0, pct))
    idx = round(clamped / 100 * 8)
    idx = max(1 if clamped > 0 else 0, min(8, idx))
    color = _multi_ramp(clamped, ramp)
    return f"{bg}{color}{_VBAR_EIGHTHS[idx]}{T.R}"


def _render_indicator(pct: float, ramp: list, display: str, *, bar_bg: str | None = None) -> str:
    """Render percentage as horizontal bar, vertical bar, or number."""
    if display == "horizontal":
        return _bar(pct, ramp=ramp, bar_bg=bar_bg)
    if display == "number":
        return f"{_multi_ramp(pct, ramp)}{pct:.0f}%{T.R}"
    return _vbar(pct, ramp=ramp, bar_bg=bar_bg)


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

    out = run(["git", "-C", cwd, "--no-optional-locks", "status", "--porcelain=v1", "--branch"], timeout=TIMEOUT_GIT)
    if out is None:
        return branch, indicators

    lines = out.split("\n")
    if not lines:
        return branch, indicators

    header = lines[0]

    if header.startswith("## "):
        branch_part = header[3:]
        if "..." in branch_part:
            branch = branch_part.split("...")[0]
        elif " " in branch_part:
            branch = branch_part.split(" ")[0]
        else:
            branch = branch_part
        if branch in ("HEAD", "No"):
            branch = ""

    ahead = ""
    behind = ""
    m = re.search(r"ahead (\d+)", header)
    if m:
        ahead = m.group(1)
    m = re.search(r"behind (\d+)", header)
    if m:
        behind = m.group(1)

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


# --- background refresh ------------------------------------------------------

_BG_SCRIPT = r"""
import fcntl, os, sys
from pathlib import Path
__IMPORTS__
CACHE, LOCK = Path(sys.argv[1]), Path(sys.argv[2])
CACHE.parent.mkdir(parents=True, exist_ok=True)
def _w(data):
    tmp = str(CACHE) + f".tmp.{os.getpid()}"
    with open(tmp, "w") as f:
        f.write(data)
    os.replace(tmp, str(CACHE))
fd = os.open(str(LOCK), os.O_WRONLY | os.O_CREAT)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except (BlockingIOError, OSError):
    os.close(fd)
    sys.exit(0)
try:
__PAYLOAD__
except Exception:
    pass
finally:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
"""


def _bg_refresh(*, imports: str, payload: str, cache_file: Path, lock_file: Path,
                extra_argv: tuple = (), stdin_data: str | None = None) -> None:
    """Fire-and-forget background subprocess with flock + atomic write."""
    script = _BG_SCRIPT.replace("__IMPORTS__", imports).replace("__PAYLOAD__", payload)
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(cache_file), str(lock_file), *extra_argv],
        start_new_session=True,
        stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if stdin_data is not None:
        try:
            proc.stdin.write(stdin_data.encode())
            proc.stdin.flush()
        except (OSError, BrokenPipeError):
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass


# --- PR status ---------------------------------------------------------------

def _refresh_pr_cache_subprocess() -> None:
    """Fire-and-forget background refresh of PR cache."""
    _bg_refresh(
        imports="import json, subprocess, time",
        payload=r"""
    TIMEOUT = """ + str(TIMEOUT_GH_API) + r"""
    gql = subprocess.run(
        ["gh", "api", "graphql", "-f", "query=" + '''
        query {
            search(query: "is:open is:pr author:@me", type: ISSUE, first: """ + str(GH_PR_FETCH_LIMIT) + r""") {
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
        capture_output=True, text=True, timeout=TIMEOUT,
    )
    prs = json.loads(gql.stdout) if gql.returncode == 0 else {}
    notif = subprocess.run(
        ["gh", "api", "notifications"], capture_output=True, text=True, timeout=TIMEOUT,
    )
    unread = 0
    if notif.returncode == 0:
        for n in json.loads(notif.stdout):
            if (n.get("subject", {}).get("type") in ("PullRequest", "Issue")
                    and n.get("unread")
                    and n.get("reason") in {"comment", "mention", "author", "review_requested", "assign"}):
                unread += 1
    _w(json.dumps({"prs": prs, "unread_count": unread, "updated_at": int(time.time())}))
""",
        cache_file=PR_CACHE_FILE,
        lock_file=PR_LOCK_FILE,
    )


def get_pr_status() -> str:
    """Return formatted PR dot string from cache, trigger refresh if stale."""
    gh = check_gh_available()
    if gh == "no-gh":
        return f"{T.err}gh not installed{T.R}"
    if gh == "no-auth":
        return f"{T.err}gh auth login{T.R}"

    cache = _cached_json(PR_CACHE_FILE, API_CACHE_TTL, _refresh_pr_cache_subprocess)
    if not cache:
        return ""

    nodes = cache.get("prs", {}).get("data", {}).get("search", {}).get("nodes", [])
    if not nodes:
        return ""

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
        parts.append(f"{T.st_fail}{''.join(dots_red)}{T.R}")
    if dots_pending:
        parts.append(f"{T.st_wait}{''.join(dots_pending)}{T.R}")
    if dots_green:
        parts.append(f"{T.st_ok}{''.join(dots_green)}{T.R}")
    if dots_gray:
        parts.append(f"{T.st_none}{''.join(dots_gray)}{T.R}")

    output = "".join(parts)

    unread = cache.get("unread_count", 0)
    if unread > 0:
        output += f" {T.notif}💬{unread}{T.R}"

    return output


# --- CI status ---------------------------------------------------------------

def _ci_from_pr_cache(branch: str) -> str | None:
    """Try to get CI status from PR cache if branch matches an open PR."""
    cache = _read_json(PR_CACHE_FILE)
    if not cache:
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
    """Return CI status label for the current branch."""
    if not branch:
        return ""

    from_pr = _ci_from_pr_cache(branch)
    if from_pr is not None:
        return from_pr

    gh = check_gh_available()
    if gh != "ok":
        return ""

    remote_url = read_remote_url(cwd)
    if not remote_url:
        return ""

    parsed = _parse_owner_repo(remote_url)
    if not parsed:
        return ""
    owner, repo = parsed

    cache_file = CI_CACHE_DIR / f"{owner}_{repo}_{branch}.json"

    if is_cache_fresh(cache_file, API_CACHE_TTL):
        data = _read_json(cache_file)
        if data:
            return _format_ci_label(data.get("conclusion"))

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
            cache_file.write_text(json.dumps({"conclusion": "none"}))
        except OSError:
            pass
        return _format_ci_label("none")

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
    """Format CI conclusion as a colored 'CI' label."""
    labels = {
        "success": f"{T.st_ok}CI{T.R}",
        "failure": f"{T.st_fail}CI{T.R}",
        "pending": f"{T.st_wait}CI{T.R}",
        "none":    f"{T.st_none}CI{T.R}",
    }
    return labels.get(conclusion, f"{T.st_none}CI{T.R}")


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
    try:
        s = re.sub(r'\.\d+', '', raw)
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
                         *, ramp: list, display: str) -> str:
    """Format one limit window: '5h▅' (compact, no trailing separator)."""
    pct = max(0.0, min(100.0, utilization))
    indicator = _render_indicator(pct, ramp, display)

    time_str = ""
    if pct >= LIMITS_COUNTDOWN_THRESHOLD:
        reset_epoch = _parse_iso_utc(resets_at)
        if reset_epoch is not None:
            remaining_min = max(0, int((reset_epoch - time.time()) / 60))
            time_str = f"{T.lim_time}{_format_duration(remaining_min)}{T.R}"
    return f"{T.dir_parent}{label}{T.R} {indicator}{time_str}"


def _refresh_limits_cache_subprocess() -> None:
    """Fire-and-forget background refresh of limits cache."""
    token = _read_oauth_token()
    if not token:
        return
    _bg_refresh(
        imports="import json\nfrom urllib.request import Request, urlopen",
        payload=r"""
    req = Request(sys.argv[3])
    req.add_header("Authorization", f"Bearer {sys.argv[4]}")
    req.add_header("anthropic-beta", "oauth-2025-04-20")
    resp = urlopen(req, timeout=""" + str(LIMITS_HTTP_TIMEOUT) + r""")
    _w(json.dumps(json.loads(resp.read())))
""",
        cache_file=LIMITS_CACHE_FILE,
        lock_file=LIMITS_LOCK_FILE,
        extra_argv=(LIMITS_API_URL, token),
    )


def provider_limits(input_json: str, cwd: str, show: list[str] | None = None) -> str:
    """Built-in provider: API usage limits (5h/7d windows) + context window."""
    if show is not None and not show:
        return ""
    sections = set(show) if show else {"5h", "7d", "ctx"}
    bars: list[str] = []

    if "5h" in sections or "7d" in sections:
        data = _cached_json(LIMITS_CACHE_FILE, LIMITS_CACHE_TTL, _refresh_limits_cache_subprocess)
        if data:
            five = data.get("five_hour", {})
            seven = data.get("seven_day", {})
            u5 = five.get("utilization", 0)
            u7 = seven.get("utilization", 0)
            if u7 >= 100:
                if "7d" in sections:
                    bars.append(_format_limit_window(u7, seven.get("resets_at", ""), "7d",
                                                     ramp=INDICATOR_CONFIG["7d"]["ramp"], display=INDICATOR_CONFIG["7d"]["display"]))
            else:
                if "5h" in sections:
                    bars.append(_format_limit_window(u5, five.get("resets_at", ""), "5h",
                                                     ramp=INDICATOR_CONFIG["5h"]["ramp"], display=INDICATOR_CONFIG["5h"]["display"]))
                if "7d" in sections:
                    bars.append(_format_limit_window(u7, seven.get("resets_at", ""), "7d",
                                                     ramp=INDICATOR_CONFIG["7d"]["ramp"], display=INDICATOR_CONFIG["7d"]["display"]))
        else:
            if "5h" in sections:
                bars.append(f"{T.dir_parent}5h{T.R} {DIM}N/A{T.R}")
            if "7d" in sections:
                bars.append(f"{T.dir_parent}7d{T.R} {DIM}N/A{T.R}")

    if "ctx" in sections:
        try:
            inp = json.loads(input_json)
            remaining = inp.get("context_window", {}).get("remaining_percentage")
            if remaining is not None:
                used = 100 - remaining
                ctx_bar = _render_indicator(used, INDICATOR_CONFIG["ctx"]["ramp"],
                                            INDICATOR_CONFIG["ctx"]["display"])
                bars.append(f"{T.dir_parent}ctx{T.R} {ctx_bar}")
            else:
                bars.append(f"{T.dir_parent}ctx{T.R} {DIM}N/A{T.R}")
        except (json.JSONDecodeError, KeyError, TypeError):
            bars.append(f"{T.dir_parent}ctx{T.R} {DIM}N/A{T.R}")

    return SEP_LIMITS.join(bars)


def provider_vibes(input_json: str, cwd: str, *, show=None) -> str:
    """Built-in provider: 7d pace label (vibes indicator)."""
    data = _cached_json(LIMITS_CACHE_FILE, LIMITS_CACHE_TTL, _refresh_limits_cache_subprocess)
    if not data:
        return ""
    seven = data.get("seven_day", {})
    return _7d_pace_label(seven.get("utilization", 0), seven.get("resets_at", ""))


# --- slot providers ----------------------------------------------------------

def provider_path(input_json: str, cwd: str, *, show=None) -> str:
    """Built-in provider: directory name (parent/current/)."""
    return get_dir_name(cwd)


def provider_git(input_json: str, cwd: str, show: list[str] | None = None) -> str:
    """Built-in provider: git branch + status + CI + PR."""
    if show is not None and not show:
        return ""
    sections = set(show) if show else {"branch", "ci", "pr", "notif"}

    need_branch = "branch" in sections or "ci" in sections
    need_pr = "pr" in sections or "notif" in sections

    with ThreadPoolExecutor(max_workers=2) as pool:
        git_future = pool.submit(get_git_info, cwd) if need_branch else None
        pr_future = pool.submit(get_pr_status) if need_pr else None

        branch, git_status = "", ""
        if git_future:
            try:
                branch, git_status = git_future.result()
            except Exception:
                pass

        pr_status = ""
        if pr_future:
            try:
                pr_status = pr_future.result()
            except Exception:
                pass

    ci_label = ""
    if branch and "ci" in sections:
        try:
            ci_label = get_ci_status(cwd, branch)
        except Exception:
            ci_label = ""

    if need_branch and not branch:
        return ""

    line = ""
    if "branch" in sections and branch:
        line = f"{T.branch_sign}{BRANCH_LABEL}{T.R}{T.branch_name}{branch}{T.R}"
        if git_status:
            line += git_status
    if ci_label:
        line += f"{SEP_GIT}{ci_label}" if line else ci_label
    if pr_status:
        if "notif" not in sections:
            pr_status = re.sub(r"\s*\x1b\[[^m]*m💬\d+\x1b\[0m$", "", pr_status)
        if "pr" not in sections:
            m = re.search(r"(\x1b\[[^m]*m💬\d+\x1b\[0m)$", pr_status)
            pr_status = m.group(1) if m else ""
        if pr_status:
            line += f"{SEP_GIT}{pr_status}" if line else pr_status
    return line


PROVIDERS: dict[str, callable] = {
    "path": provider_path,
    "git": provider_git,
    "limits": provider_limits,
    "vibes": provider_vibes,
}

PROVIDER_SECTIONS: dict[str, tuple[str, ...]] = {
    "git": ("branch", "ci", "pr", "notif"),
    "limits": ("5h", "7d", "ctx"),
}


# --- external slot executor --------------------------------------------------

def _refresh_external_slot_subprocess(command: str, input_json: str,
                                      cache_file: Path, lock_file: Path) -> None:
    """Fire-and-forget background refresh of an external slot cache."""
    _bg_refresh(
        imports="import subprocess",
        payload=r"""
    env = {**os.environ, "FORCE_COLOR": "1"}
    r = subprocess.run(
        sys.argv[3], shell=True, input=sys.stdin.read(),
        capture_output=True, text=True, timeout=""" + str(SLOT_TIMEOUT) + r""", env=env,
    )
    if r.returncode == 0 and r.stdout.strip():
        _w(r.stdout.strip())
""",
        cache_file=cache_file,
        lock_file=lock_file,
        extra_argv=(command,),
        stdin_data=input_json,
    )


def _check_command_available(command: str) -> str | None:
    """Return None if command's executable is available, or a placeholder string."""
    parts = command.split()
    if not parts:
        return None
    exe = parts[0]
    if os.path.isabs(exe):
        found = os.path.isfile(exe) and os.access(exe, os.X_OK)
    else:
        found = shutil.which(exe) is not None
    if found:
        return None
    # Prefer basename of first arg (script) over the interpreter itself
    label = os.path.basename(parts[1]) if len(parts) > 1 else os.path.basename(exe)
    return f"{T.sep}{DIM}[{label}: not found]{RESET}"


def run_external_slot(command: str, input_json: str, ttl: int) -> str:
    """Return external slot output from cache, trigger bg refresh if stale."""
    expanded = os.path.expanduser(command)
    placeholder = _check_command_available(expanded)
    if placeholder is not None:
        return placeholder
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

def execute_slots(slots: list, input_json: str, cwd: str) -> list[str]:
    """Execute all slots in parallel, return ordered list of non-empty lines."""
    lines: list[list[dict]] = []
    for slot in slots:
        if isinstance(slot, list):
            enabled = [s for s in slot if s.get("enabled", True)]
            if enabled:
                lines.append(enabled)
        elif slot.get("enabled", True):
            lines.append([slot])

    all_widgets: list[tuple[int, int, dict]] = []
    for li, widgets in enumerate(lines):
        for wi, w in enumerate(widgets):
            all_widgets.append((li, wi, w))

    def _run_slot(slot: dict) -> str:
        provider = slot.get("provider")
        if provider:
            func = PROVIDERS.get(provider)
            if func:
                return func(input_json, cwd, show=slot.get("show"))
            return ""
        command = slot.get("command")
        if command:
            ttl = slot.get("ttl", SLOT_CACHE_TTL)
            return run_external_slot(command, input_json, ttl)
        return ""

    grid: list[list[str]] = [[""] * len(ws) for ws in lines]
    with ThreadPoolExecutor(max_workers=min(max(len(all_widgets), 1), 16)) as pool:
        futures = {pool.submit(_run_slot, w): (li, wi)
                   for li, wi, w in all_widgets}
        for future in as_completed(futures):
            li, wi = futures[future]
            try:
                grid[li][wi] = future.result()
            except (RuntimeError, ValueError, OSError, subprocess.SubprocessError):
                grid[li][wi] = ""

    result: list[str] = []
    for parts in grid:
        joined = SEP_EXTRA.join(p for p in parts if p)
        if joined:
            result.append(joined)
    return result


def render(lines: list[str]) -> str:
    """Join slot output lines."""
    return "\n".join(lines)


# --- theme editor config I/O ------------------------------------------------

def _load_validated_config() -> dict:
    """Read config.json, validate, exit(1) on errors. Return parsed dict."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        config = json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"config: failed to parse JSON: {exc}", file=sys.stderr)
        print(f"Fix: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    errors = _validate_config(config)
    if errors:
        for e in errors:
            print(f"config: {e}", file=sys.stderr)
        print(f"Fix: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    return config


def _theme_from_config(config: dict) -> dict[str, ThemeEntry]:
    """Extract theme entries from validated config."""
    theme = {k: v.copy() for k, v in DEFAULTS.items()}
    for key, val in config.get("theme", {}).items():
        if key in theme and isinstance(val, dict):
            theme[key] = ThemeEntry(
                fg=val.get("fg"), bg=val.get("bg"),
                attrs=val.get("attrs", []),
            )
    return theme


def _settings_from_config(config: dict) -> dict[str, str]:
    """Extract settings from validated config."""
    settings = {s.key: s.default for s in SETTINGS_DEFS}
    for s in SETTINGS_DEFS:
        val = config.get("settings", {}).get(s.key)
        if isinstance(val, str) and val in s.options:
            settings[s.key] = val
    return settings


def save_theme(theme: dict[str, ThemeEntry],
               settings: dict[str, str] | None = None) -> str:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if CONFIG_FILE.exists():
        try:
            existing = json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    data: dict = {}

    if "slots" in existing:
        data["slots"] = existing["slots"]

    settings_out: dict = {}
    if settings:
        for s in SETTINGS_DEFS:
            val = settings.get(s.key, s.default)
            if val != s.default:
                settings_out[s.key] = val
    if settings_out:
        data["settings"] = settings_out

    theme_out: dict = {}
    for key, entry in theme.items():
        d: dict = {}
        if entry.fg is not None:
            d["fg"] = entry.fg
        if entry.bg is not None:
            d["bg"] = entry.bg
        if entry.attrs:
            d["attrs"] = entry.attrs
        theme_out[key] = d
    data["theme"] = theme_out

    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(CONFIG_DIR), prefix=".theme.", suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            f.write(json.dumps(data, indent=2) + "\n")
        os.replace(tmp_path, str(CONFIG_FILE))
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return str(CONFIG_FILE)


# --- theme editor TUI helpers -----------------------------------------------

def _render_ramp_strip(ramp_name: str, width: int = 20) -> str:
    """Render a horizontal color strip showing the ramp gradient."""
    waypoints = RAMP_PRESETS.get(ramp_name)
    if not waypoints:
        return ""
    bg = T.lim_bar_bg
    parts: list[str] = []
    for i in range(width):
        pct = i / (width - 1) * 100
        c = _multi_ramp_color(pct, waypoints)
        parts.append(f"{bg}{fg256(c)}█{RESET}")
    return "".join(parts)


def _render_demo_number(pct: float, ramp_name: str, width: int = 0) -> str:
    """Render a colored percentage number for demo. Pad to width if given."""
    waypoints = RAMP_PRESETS.get(ramp_name, RAMP_PRESETS[_SETTINGS_DEFAULTS["5h_ramp"]])
    c = _multi_ramp_color(pct, waypoints)
    text = f"{pct:.0f}%"
    if width:
        text = text.rjust(width)
    return f"{fg256(c)}{text}{RESET}"


# --- theme editor: Editor class ----------------------------------------------

class Editor:
    def __init__(self):
        config = _load_validated_config()
        self.theme = _theme_from_config(config)
        self.settings = _settings_from_config(config)
        self._saved_theme = {k: v.copy() for k, v in self.theme.items()}
        self._saved_settings = dict(self.settings)
        self.cursor = 0
        self.clipboard: ThemeEntry | None = None
        self.mode = "nav"
        self.color_cursor = 0
        self.attr_cursor = 0
        self.settings_cursor = 0
        self._anim_pct = 0.0
        self._anim_ascending = True
        self.msg = ""
        self.running = True

    # --- dirty tracking ---

    def _mark_saved(self):
        self._saved_theme = {k: v.copy() for k, v in self.theme.items()}
        self._saved_settings = dict(self.settings)

    def _has_changes(self) -> bool:
        if self.settings != self._saved_settings:
            return True
        for key in self.theme:
            cur, saved = self.theme[key], self._saved_theme[key]
            if cur.fg != saved.fg or cur.bg != saved.bg or cur.attrs != saved.attrs:
                return True
        return False

    def _diff_lines(self) -> list[str]:
        lines: list[str] = []
        for elem in ELEMENTS:
            cur, saved = self.theme[elem.key], self._saved_theme[elem.key]
            diffs: list[str] = []
            if cur.fg != saved.fg:
                diffs.append(f"fg {saved.fg}→{cur.fg}")
            if cur.bg != saved.bg:
                diffs.append(f"bg {saved.bg}→{cur.bg}")
            if cur.attrs != saved.attrs:
                old_a = ",".join(saved.attrs) or "none"
                new_a = ",".join(cur.attrs) or "none"
                diffs.append(f"attrs {old_a}→{new_a}")
            if diffs:
                lines.append(f"  {elem.label} ({elem.key}): {', '.join(diffs)}")
        for sdef in SETTINGS_DEFS:
            cur_val = self.settings.get(sdef.key, sdef.default)
            saved_val = self._saved_settings.get(sdef.key, sdef.default)
            if cur_val != saved_val:
                cur_display = _SEP_DISPLAY.get(cur_val, cur_val) if sdef.key in ("separator", "git_separator", "limits_separator") else cur_val
                saved_display = _SEP_DISPLAY.get(saved_val, saved_val) if sdef.key in ("separator", "git_separator", "limits_separator") else saved_val
                lines.append(f"  {sdef.label}: {saved_display}→{cur_display}")
        return lines

    @staticmethod
    def _config_path_display() -> str:
        try:
            return f"~/{CONFIG_FILE.relative_to(Path.home())}"
        except ValueError:
            return str(CONFIG_FILE)

    # --- preview rendering ---

    def _styled(self, key: str, text: str) -> str:
        entry = self.theme[key]
        if key == ELEMENTS[self.cursor].key:
            if self.mode in ("fg", "bg"):
                entry = entry.copy()
                if self.mode == "fg":
                    entry.fg = self.color_cursor if self.color_cursor >= 0 else None
                else:
                    entry.bg = self.color_cursor if self.color_cursor >= 0 else None
            elif self.mode == "attr":
                attr_name = ATTRS_AVAILABLE[self.attr_cursor][0]
                entry = entry.copy()
                if attr_name == "none":
                    entry.attrs.clear()
                elif attr_name not in entry.attrs:
                    entry.attrs.append(attr_name)
                else:
                    entry.attrs.remove(attr_name)
        style = build_style(entry)
        return f"{style}{text}{RESET}"

    @staticmethod
    def _visual_len(text: str) -> int:
        n = 0
        for ch in text:
            if unicodedata.east_asian_width(ch) in ("W", "F"):
                n += 2
            else:
                n += 1
        return n

    def render_preview(self) -> tuple[str, str]:
        cur = ELEMENTS[self.cursor].key
        sep_char = self.settings["separator"]
        git_sep_char = self.settings["git_separator"]

        def _sep_segment(kind: str) -> tuple[str | None, str]:
            ch = sep_char if kind == "sep" else git_sep_char
            return ("sep", f" {ch} ") if ch else (None, " ")

        # Build segments from ELEMENTS order — single source of truth
        segments: list[tuple[str | None, str]] = []
        prev_group = None
        for elem in ELEMENTS:
            # Insert gap before element
            if elem.gap in ("sep", "git_sep"):
                segments.append(_sep_segment(elem.gap))
            elif elem.gap:
                segments.append((None, elem.gap))
            # Lim group content rendered by _append_limits_demo
            if elem.group == "lim":
                continue
            # After CI group ends, inject PR dots block
            if prev_group == "ci" and elem.group != "ci":
                segments.append(_sep_segment("git_sep"))
                for dot_key, dot_text in [("st_ok", "⁕⁕⁕"), ("st_fail", "⁕"), ("st_wait", "⁕⁕"), ("st_none", "⁕")]:
                    segments.append((dot_key, dot_text))
            prev_group = elem.group
            # Sep element renders as the configured separator character
            if elem.key == "sep":
                segments.append(_sep_segment("sep"))
            else:
                segments.append((elem.key, elem.sample))

        preview_parts: list[str] = []
        caret_chars: list[str] = []

        for key, text in segments:
            vlen = self._visual_len(text)
            if key is not None:
                preview_parts.append(self._styled(key, text))
                caret_chars.extend(["^" if key == cur else " "] * vlen)
            else:
                preview_parts.append(text)
                caret_chars.extend([" "] * vlen)

        self._append_limits_demo(preview_parts, caret_chars, cur)

        preview = "".join(preview_parts)
        carets = f"{DIM}{''.join(caret_chars)}{RESET}"
        return preview, carets

    def _themed_bar_bg(self) -> str:
        """Resolve bar background ANSI from current theme (with live preview)."""
        entry = self.theme.get("lim_bar_bg")
        if entry is None:
            return T.lim_bar_bg
        bg_val = entry.bg
        if ELEMENTS[self.cursor].key == "lim_bar_bg" and self.mode == "bg":
            bg_val = self.color_cursor if self.color_cursor >= 0 else None
        return bg256(bg_val) if bg_val is not None else T.lim_bar_bg

    def _append_limits_demo(self, parts: list[str], carets: list[str], cur: str):
        bar_bg = self._themed_bar_bg()

        anim = self._is_anim_active()
        p = self._anim_pct
        demos = [
            ("5h", p if anim else 30, None if anim else "4h26m"),
            ("7d", p if anim else 55, None),
            ("ctx", p if anim else 40, None),
        ]
        lim_sep = self.settings.get("limits_separator", "")
        lim_sep_text = f" {lim_sep} " if lim_sep else " "
        for i, (label, pct, time_text) in enumerate(demos):
            if i > 0:
                parts.append(lim_sep_text if not lim_sep else self._styled("sep", lim_sep_text))
                carets.extend([" "] * self._visual_len(lim_sep_text))

            lbl = f"{label} "
            parts.append(self._styled("lim_time", lbl))
            carets.extend(["^" if cur == "lim_time" else " "] * self._visual_len(lbl))

            ramp_name = self.settings.get(f"{label}_ramp", _SETTINGS_DEFAULTS[f"{label}_ramp"])
            display = self.settings.get(f"{label}_display", _SETTINGS_DEFAULTS[f"{label}_display"])
            if display == "number":
                bar_text = _render_demo_number(pct, ramp_name, width=4)
                bar_vlen = 4
            elif display == "horizontal":
                bar_text = _bar(pct, ramp=RAMP_PRESETS[ramp_name], bar_bg=bar_bg)
                bar_vlen = 5
            else:
                bar_text = _vbar(pct, ramp=RAMP_PRESETS[ramp_name], bar_bg=bar_bg)
                bar_vlen = 1
            parts.append(bar_text)
            carets.extend(["^" if cur == "lim_bar_bg" else " "] * bar_vlen)

            if time_text:
                parts.append(self._styled("lim_time", time_text))
                carets.extend(["^" if cur == "lim_time" else " "] * len(time_text))

    # --- legend ---

    def render_legend(self) -> list[str]:
        elem = ELEMENTS[self.cursor]
        entry = self.theme[elem.key]

        parts: list[str] = []
        if "fg" in elem.props:
            fg_s = f"{fg256(entry.fg)}██{RESET} {entry.fg}" if entry.fg is not None else f"{DIM}default{RESET}"
            parts.append(f"FG: {fg_s}")
        if "bg" in elem.props:
            bg_s = f"{bg256(entry.bg)}  {RESET} {entry.bg}" if entry.bg is not None else f"{DIM}default{RESET}"
            parts.append(f"BG: {bg_s}")
        if "attrs" in elem.props:
            attr_s = ", ".join(entry.attrs) if entry.attrs else f"{DIM}none{RESET}"
            parts.append(f"Attrs: {attr_s}")

        return [
            f"{BOLD}{elem.label}{RESET}  {DIM}({elem.key}){RESET}  {DIM}{elem.desc}{RESET}",
            "",
            "   ".join(parts),
        ]

    # --- color picker ---

    def render_color_grid(self, is_bg: bool) -> list[str]:
        lines: list[str] = []
        sel = self.color_cursor
        entry = self.theme[ELEMENTS[self.cursor].key]
        active = entry.bg if is_bg else entry.fg

        elem_bg = bg256(entry.bg) if entry.bg is not None else ""

        def cell(n: int) -> str:
            if is_bg:
                block = f"{bg256(n)}  {RESET}"
            else:
                block = f"{elem_bg}{fg256(n)}[]{RESET}"
            if n == sel:
                return f"{BLINK}{REVERSE}{block}{RESET}"
            if n == active:
                return f"{UNDERLINE}{block}{RESET}"
            return block

        is_default = active is None
        dflt_arrow = f"{BLINK}{REVERSE}▸{RESET}" if sel == -1 else " "
        dflt_mark = f"{BOLD}●{RESET}" if is_default else f"{DIM}○{RESET}"
        lines.append(f"  {dflt_arrow} {dflt_mark} default {DIM}(transparent){RESET}")
        lines.append("")

        lines.append("  " + " ".join(cell(i) for i in range(8)))
        lines.append("  " + " ".join(cell(i) for i in range(8, 16)))
        lines.append("")

        for g in range(6):
            row_cells = []
            for r in range(6):
                for b in range(6):
                    row_cells.append(cell(_rgb_cube(r, g, b)))
                if r < 5:
                    row_cells.append(" ")
            lines.append("  " + "".join(row_cells))
        lines.append("")

        lines.append("  " + "".join(cell(232 + i) for i in range(24)))

        return lines

    # --- attribute picker ---

    def render_attr_picker(self) -> list[str]:
        entry = self.theme[ELEMENTS[self.cursor].key]
        lines: list[str] = []
        color = ""
        if entry.fg is not None:
            color += fg256(entry.fg)
        if entry.bg is not None:
            color += bg256(entry.bg)
        for i, (name, sgr, desc) in enumerate(ATTRS_AVAILABLE):
            arrow = "▸" if i == self.attr_cursor else " "
            if name == "none":
                active_mark = f"{BOLD}●{RESET}" if not entry.attrs else f"{DIM}○{RESET}"
                lines.append(f"  {arrow} {active_mark} {color}{desc}{RESET}")
            else:
                active_mark = f"{BOLD}●{RESET}" if name in entry.attrs else f"{DIM}○{RESET}"
                lines.append(f"  {arrow} {active_mark} {color}{sgr}{desc}{RESET}")
        return lines

    # --- settings panel ---

    def _render_setting_preview(self, sdef: SettingDef, val: str) -> str:
        bar_bg = self._themed_bar_bg()

        if sdef.key in ("5h_ramp", "7d_ramp", "ctx_ramp"):
            prefix = sdef.key.split("_")[0]
            display = self.settings.get(f"{prefix}_display", _SETTINGS_DEFAULTS[f"{prefix}_display"])
            if display == "number":
                bars = " ".join(_render_demo_number(p, val) for p in range(10, 100, 10))
            elif display == "horizontal":
                bars = " ".join(_bar(p, 3, ramp=RAMP_PRESETS[val], bar_bg=bar_bg) for p in (20, 50, 80))
            else:
                bars = " ".join(_vbar(p, ramp=RAMP_PRESETS[val], bar_bg=bar_bg) for p in range(5, 100, 5))
            return f"  {bars}"
        elif sdef.key in ("5h_display", "7d_display", "ctx_display"):
            prefix = sdef.key.split("_")[0]
            ramp = self.settings.get(f"{prefix}_ramp", _SETTINGS_DEFAULTS[f"{prefix}_ramp"])
            if val == "number":
                return f"  {_render_demo_number(60, ramp)}"
            elif val == "horizontal":
                return f"  {_bar(60, 8, ramp=RAMP_PRESETS[ramp], bar_bg=bar_bg)}"
            else:
                bars = " ".join(_vbar(p, ramp=RAMP_PRESETS[ramp], bar_bg=bar_bg) for p in (10, 30, 50, 70, 90))
                return f"  {bars}"
        elif sdef.key in ("separator", "git_separator", "limits_separator"):
            sep_entry = self.theme.get("sep")
            sep_style = build_style(sep_entry) if sep_entry else fg256(8)
            sep_vis = f" {sep_style}{val}{RESET} " if val else " "
            labels = {"separator": ("path", "git", "limits"),
                      "git_separator": ("branch", "CI", "PR"),
                      "limits_separator": ("5h", "7d", "ctx")}
            parts = sep_vis.join(f"{DIM}{l}{RESET}" for l in labels[sdef.key])
            return f"  {parts}"
        return ""

    def render_settings(self) -> list[str]:
        lines: list[str] = []
        for i, sdef in enumerate(SETTINGS_DEFS):
            arrow = "▸" if i == self.settings_cursor else " "
            val = self.settings[sdef.key]
            opt_parts: list[str] = []
            for opt in sdef.options:
                label = _SEP_DISPLAY.get(opt, opt) if sdef.key in ("separator", "git_separator", "limits_separator") else opt
                if opt == val:
                    opt_parts.append(f"{BOLD}{REVERSE} {label} {RESET}")
                else:
                    opt_parts.append(f" {DIM}{label}{RESET} ")
            opts_str = " ".join(opt_parts)
            preview = self._render_setting_preview(sdef, val)
            lines.append(f"  {arrow} {sdef.label:20s} {opts_str}{preview}")
        return lines

    # --- full render ---

    def render(self):
        out: list[str] = []
        out.append(CLEAR_SCREEN)
        out.append(HIDE_CURSOR)

        out.append(f"  {BOLD}Claude Code Statusline — Theme Editor{RESET}\r\n\r\n")

        preview, carets = self.render_preview()
        legend = self.render_legend()
        out.append(f"  {preview}\r\n  {carets}\r\n\r\n")
        for line in legend:
            out.append(f"  {line}\r\n")

        if self.mode in ("fg", "bg", "attr"):
            elem = ELEMENTS[self.cursor]
            entry = self.theme[elem.key]
            pad = 0
            fg_vis = (3 + len(str(entry.fg))) if entry.fg is not None else 7
            bg_vis = (3 + len(str(entry.bg))) if entry.bg is not None else 7
            if self.mode == "fg":
                pad = 4
                sel = self.color_cursor
                hint = f"{fg256(sel)}██{RESET} {sel}" if sel >= 0 else f"{DIM}default{RESET}"
            elif self.mode == "bg":
                pad = (4 + fg_vis + 3) if "fg" in elem.props else 0
                pad += 4
                sel = self.color_cursor
                hint = f"{bg256(sel)}  {RESET} {sel}" if sel >= 0 else f"{DIM}default{RESET}"
            else:
                if "fg" in elem.props:
                    pad += 4 + fg_vis + 3
                if "bg" in elem.props:
                    pad += 4 + bg_vis + 3
                pad += 7
                attr_name = ATTRS_AVAILABLE[self.attr_cursor][0]
                tentative = list(entry.attrs)
                if attr_name == "none":
                    tentative.clear()
                elif attr_name not in tentative:
                    tentative.append(attr_name)
                else:
                    tentative.remove(attr_name)
                hint = ", ".join(tentative) if tentative else f"{DIM}none{RESET}"
            out.append(f"  {' ' * pad}{hint}\r\n")

        out.append("\r\n")

        if self.mode == "fg":
            out.append(f"  {BOLD}Pick FG color{RESET}  {DIM}(arrows navigate, Enter select, Esc cancel){RESET}\r\n")
            for line in self.render_color_grid(is_bg=False):
                out.append(f"{line}\r\n")
        elif self.mode == "bg":
            out.append(f"  {BOLD}Pick BG color{RESET}  {DIM}(arrows navigate, Enter select, Esc cancel){RESET}\r\n")
            for line in self.render_color_grid(is_bg=True):
                out.append(f"{line}\r\n")
        elif self.mode == "attr":
            out.append(f"  {BOLD}Toggle attributes{RESET}  {DIM}(↑↓ navigate, Space toggle, Esc done){RESET}\r\n")
            for line in self.render_attr_picker():
                out.append(f"{line}\r\n")
        elif self.mode == "settings":
            out.append(f"  {BOLD}Global Settings{RESET}  {DIM}(↑↓ navigate, ←→ change, Enter apply, Esc cancel){RESET}\r\n\r\n")
            for line in self.render_settings():
                out.append(f"{line}\r\n")
        elif self.mode == "quit":
            out.append(f"  {BOLD}Unsaved changes:{RESET}\r\n\r\n")
            for line in self._diff_lines():
                out.append(f"  {line}\r\n")
            out.append(f"\r\n  {DIM}Save to {self._config_path_display()}?{RESET}\r\n")
            K = f"{RESET}\033[97m"
            D = f"{RESET}"
            out.append(f"\r\n  {K}y{D} save & quit   {K}n{D} discard & quit   {K}q{D}/{K}Esc{D} cancel{RESET}\r\n")

        out.append("\r\n")
        if self.mode == "nav":
            K = f"{RESET}\033[97m"
            D = f"{RESET}"
            X = f"{RESET}{fg256(239)}"
            props = ELEMENTS[self.cursor].props
            has_changes = self._has_changes()
            def _k(key: str, label: str, active: bool) -> str:
                return f"{K}{key}{D} {label}" if active else f"{X}{key} {label}"
            keys: list[str] = [
                f"{D}← → navigate",
                _k("f", "fg", "fg" in props),
                _k("b", "bg", "bg" in props),
                _k("a", "attrs", "attrs" in props),
                f"{K}g{D} settings",
                f"{K}c{D} copy", f"{K}v{D} paste",
                _k("s", "save", has_changes),
                f"{K}r{D} reset", f"{K}q{D} quit",
            ]
            out.append(f"  {'   '.join(keys)}{RESET}\r\n")

        if self.msg:
            out.append(f"\r\n  {self.msg}\r\n")

        sys.stdout.write("".join(out))
        sys.stdout.flush()

    # --- key handling ---

    def handle_key(self, key: str):
        key = _CYRILLIC_MAP.get(key, key)
        self.msg = ""

        if self.mode == "quit":
            self._handle_quit(key)
        elif self.mode == "nav":
            self._handle_nav(key)
        elif self.mode in ("fg", "bg"):
            self._handle_color(key)
        elif self.mode == "attr":
            self._handle_attr(key)
        elif self.mode == "settings":
            self._handle_settings(key)

    def _handle_quit(self, key: str):
        if key == "y":
            save_theme(self.theme, self.settings)
            self._mark_saved()
            self.running = False
        elif key == "n":
            self.running = False
        elif key in ("q", "\x1b"):
            self.mode = "nav"
            self.msg = ""

    def _handle_nav(self, key: str):
        if key == "q":
            if self._has_changes():
                self.mode = "quit"
            else:
                self.running = False
        elif key == LEFT:
            self.cursor = (self.cursor - 1) % len(ELEMENTS)
        elif key == RIGHT:
            self.cursor = (self.cursor + 1) % len(ELEMENTS)
        elif key == "f":
            elem = ELEMENTS[self.cursor]
            if "fg" not in elem.props:
                return
            self.mode = "fg"
            e = self.theme[elem.key]
            self.color_cursor = e.fg if e.fg is not None else -1
        elif key == "b":
            elem = ELEMENTS[self.cursor]
            if "bg" not in elem.props:
                return
            self.mode = "bg"
            e = self.theme[elem.key]
            self.color_cursor = e.bg if e.bg is not None else -1
        elif key == "a":
            if "attrs" not in ELEMENTS[self.cursor].props:
                return
            self.mode = "attr"
            self.attr_cursor = 0
        elif key == "g":
            self.mode = "settings"
            self.settings_cursor = 0
            self._settings_snapshot = dict(self.settings)
        elif key == "s":
            if not self._has_changes():
                return
            save_theme(self.theme, self.settings)
            self._mark_saved()
            self.msg = f"Saved → {self._config_path_display()}"
        elif key == "r":
            k = ELEMENTS[self.cursor].key
            d = DEFAULTS[k]
            self.theme[k] = ThemeEntry(fg=d.fg, bg=d.bg, attrs=list(d.attrs))
            self.msg = f"Reset {k} to default"
        elif key == "R":
            self.theme = {k: ThemeEntry(fg=v.fg, bg=v.bg, attrs=list(v.attrs))
                          for k, v in DEFAULTS.items()}
            self.msg = "Reset ALL to defaults"
        elif key == "c":
            e = self.theme[ELEMENTS[self.cursor].key]
            self.clipboard = e.copy()
            self.msg = f"Copied {ELEMENTS[self.cursor].label}"
        elif key == "v":
            if self.clipboard:
                elem = ELEMENTS[self.cursor]
                cur = self.theme[elem.key]
                self.theme[elem.key] = ThemeEntry(
                    fg=self.clipboard.fg if "fg" in elem.props else cur.fg,
                    bg=self.clipboard.bg if "bg" in elem.props else cur.bg,
                    attrs=list(self.clipboard.attrs) if "attrs" in elem.props else list(cur.attrs))
                self.msg = f"Pasted → {elem.label}"
            else:
                self.msg = "Nothing to paste"

    def _handle_color(self, key: str):
        if key == ESC_KEY:
            self.mode = "nav"
        elif self.color_cursor == -1:
            if key == DOWN:
                self.color_cursor = 0
            elif key == ENTER:
                k = ELEMENTS[self.cursor].key
                if self.mode == "fg":
                    self.theme[k].fg = None
                else:
                    self.theme[k].bg = None
                self.mode = "nav"
        else:
            if key == RIGHT:
                self.color_cursor = _grid_move(self.color_cursor, "right")
            elif key == LEFT:
                self.color_cursor = _grid_move(self.color_cursor, "left")
            elif key == DOWN:
                self.color_cursor = _grid_move(self.color_cursor, "down")
            elif key == UP:
                row_i, _ = _COLOR_POS[self.color_cursor]
                if row_i == 0:
                    self.color_cursor = -1
                else:
                    self.color_cursor = _grid_move(self.color_cursor, "up")
            elif key == "d":
                self.color_cursor = -1
            elif key == ENTER:
                k = ELEMENTS[self.cursor].key
                if self.mode == "fg":
                    self.theme[k].fg = self.color_cursor
                else:
                    self.theme[k].bg = self.color_cursor
                self.mode = "nav"

    def _handle_attr(self, key: str):
        if key == ESC_KEY:
            self.mode = "nav"
        elif key == UP:
            self.attr_cursor = (self.attr_cursor - 1) % len(ATTRS_AVAILABLE)
        elif key == DOWN:
            self.attr_cursor = (self.attr_cursor + 1) % len(ATTRS_AVAILABLE)
        elif key == " ":
            name = ATTRS_AVAILABLE[self.attr_cursor][0]
            entry = self.theme[ELEMENTS[self.cursor].key]
            if name == "none":
                entry.attrs.clear()
            elif name in entry.attrs:
                entry.attrs.remove(name)
            else:
                entry.attrs.append(name)

    def _handle_settings(self, key: str):
        if key == "\r":
            self.mode = "nav"
            self.msg = f"{DIM}Settings applied{RESET}"
        elif key == ESC_KEY:
            self.settings = dict(self._settings_snapshot)
            self.mode = "nav"
            self.msg = f"{DIM}Settings reverted{RESET}"
        elif key == UP:
            self.settings_cursor = (self.settings_cursor - 1) % len(SETTINGS_DEFS)
        elif key == DOWN:
            self.settings_cursor = (self.settings_cursor + 1) % len(SETTINGS_DEFS)
        elif key in (LEFT, RIGHT):
            sdef = SETTINGS_DEFS[self.settings_cursor]
            cur_val = self.settings[sdef.key]
            try:
                idx = sdef.options.index(cur_val)
            except ValueError:
                idx = 0
            if key == RIGHT:
                idx = (idx + 1) % len(sdef.options)
            else:
                idx = (idx - 1) % len(sdef.options)
            self.settings[sdef.key] = sdef.options[idx]

    # --- terminal I/O ---

    def read_key(self) -> str:
        fd = sys.stdin.fileno()
        ch = os.read(fd, 1)
        if ch == b"\x1b":
            if select.select([fd], [], [], 0.1)[0]:
                ch2 = os.read(fd, 1)
                if ch2 == b"[":
                    ch3 = os.read(fd, 1)
                    if ch3.isdigit():
                        buf = ch3
                        while select.select([fd], [], [], 0.02)[0]:
                            c = os.read(fd, 1)
                            buf += c
                            if c.isalpha() or c == b"~":
                                break
                        return f"\x1b[{buf.decode()}"
                    return f"\x1b[{ch3.decode()}"
                if ch2 == b"O":
                    ch3 = os.read(fd, 1)
                    return f"\x1b[{ch3.decode()}"
                return f"\x1b{ch2.decode()}"
            return ESC_KEY
        b0 = ch[0]
        if b0 >= 0xC0:
            need = (2 if b0 < 0xE0 else 3 if b0 < 0xF0 else 4) - 1
            ch += os.read(fd, need)
        return ch.decode()

    # --- animation ---

    _ANIM_STEP = 5.0
    _ANIM_INTERVAL = 0.067

    def _is_anim_active(self) -> bool:
        if self.mode != "settings":
            return False
        sdef = SETTINGS_DEFS[self.settings_cursor]
        return sdef.key.endswith("_ramp") or sdef.key.endswith("_display")

    def _advance_animation(self):
        if self._anim_ascending:
            self._anim_pct += self._ANIM_STEP
            if self._anim_pct >= 100:
                self._anim_pct = 100
                self._anim_ascending = False
        else:
            self._anim_pct -= self._ANIM_STEP
            if self._anim_pct <= 0:
                self._anim_pct = 0
                self._anim_ascending = True

    def _read_key_timeout(self, timeout: float) -> str | None:
        fd = sys.stdin.fileno()
        if not select.select([fd], [], [], timeout)[0]:
            return None
        return self.read_key()

    def run(self):
        old = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin)
            while self.running:
                self.render()
                if self._is_anim_active():
                    key = self._read_key_timeout(self._ANIM_INTERVAL)
                    if key is None:
                        self._advance_animation()
                        continue
                else:
                    key = self.read_key()
                self.handle_key(key)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
            sys.stdout.write(SHOW_CURSOR + CLEAR_SCREEN)
            sys.stdout.flush()


# --- grid navigation ---------------------------------------------------------

_GRID_ROWS: list[list[int]] = [
    list(range(0, 8)),
    list(range(8, 16)),
]
for _g in range(6):
    _row = []
    for _r in range(6):
        for _b in range(6):
            _row.append(_rgb_cube(_r, _g, _b))
    _GRID_ROWS.append(_row)
_GRID_ROWS.append(list(range(232, 256)))
del _g, _r, _b, _row

_COLOR_POS: dict[int, tuple[int, int]] = {}
for _ri, _row in enumerate(_GRID_ROWS):
    for _ci, _color in enumerate(_row):
        _COLOR_POS[_color] = (_ri, _ci)
del _ri, _row, _ci, _color


def _row_visual_x(row_i: int) -> list[int]:
    n = len(_GRID_ROWS[row_i])
    if n == 8:
        return [c * 3 for c in range(n)]
    elif n == 36:
        return [c * 2 + c // 6 for c in range(n)]
    else:
        return [c * 2 for c in range(n)]


_VISUAL_X: list[list[int]] = [_row_visual_x(i) for i in range(len(_GRID_ROWS))]


def _closest_col(row_i: int, target_x: int) -> int:
    positions = _VISUAL_X[row_i]
    best = 0
    best_dist = abs(positions[0] - target_x)
    for c in range(1, len(positions)):
        dist = abs(positions[c] - target_x)
        if dist < best_dist:
            best = c
            best_dist = dist
    return best


def _grid_move(pos: int, direction: str) -> int:
    row_i, col_i = _COLOR_POS[pos]
    if direction == "left":
        col_i = max(0, col_i - 1)
    elif direction == "right":
        col_i = min(len(_GRID_ROWS[row_i]) - 1, col_i + 1)
    elif direction == "up":
        if row_i > 0:
            cur_x = _VISUAL_X[row_i][col_i]
            row_i -= 1
            col_i = _closest_col(row_i, cur_x)
    elif direction == "down":
        if row_i < len(_GRID_ROWS) - 1:
            cur_x = _VISUAL_X[row_i][col_i]
            row_i += 1
            col_i = _closest_col(row_i, cur_x)
    return _GRID_ROWS[row_i][col_i]


# Key constants
LEFT     = "\x1b[D"
RIGHT    = "\x1b[C"
UP       = "\x1b[A"
DOWN     = "\x1b[B"
ENTER    = "\r"
ESC_KEY  = "\x1b"

# ЙЦУКЕН → QWERTY mapping for Cyrillic keyboard layout
_CYRILLIC_MAP = {
    "й": "q", "а": "f", "и": "b", "ф": "a", "ы": "s",
    "к": "r", "К": "R", "в": "d", "с": "c", "м": "v",
    "п": "g",
}


# --- demo --------------------------------------------------------------------

def demo() -> None:
    """Print demo scenarios for visual testing."""
    D = PR_DOT

    def path_part() -> str:
        return f"{T.dir_name}{DEMO_DIR_NAME}{T.R}"

    def git_line(branch: str, status: str = "", ci: str = "", pr: str = "") -> str:
        if not branch:
            return ""
        line = f"{T.branch_sign}{BRANCH_LABEL}{T.R}{T.branch_name}{branch}{T.R}"
        if status:
            line += status
        if ci:
            line += f"{SEP_GIT}{ci}"
        if pr:
            line += f"{SEP_GIT}{pr}"
        return line

    def limits_bars(u5: float, r5: str, u7: float, r7: str, ctx: int) -> str:
        bars: list[str] = []
        if u7 >= 100:
            bars.append(_format_limit_window(u7, r7, "7d",
                                             ramp=INDICATOR_CONFIG["7d"]["ramp"], display=INDICATOR_CONFIG["7d"]["display"]))
        else:
            bars.append(_format_limit_window(u5, r5, "5h",
                                             ramp=INDICATOR_CONFIG["5h"]["ramp"], display=INDICATOR_CONFIG["5h"]["display"]))
            bars.append(_format_limit_window(u7, r7, "7d",
                                             ramp=INDICATOR_CONFIG["7d"]["ramp"], display=INDICATOR_CONFIG["7d"]["display"]))
        ctx_bar = _render_indicator(ctx, INDICATOR_CONFIG["ctx"]["ramp"],
                                    INDICATOR_CONFIG["ctx"]["display"])
        bars.append(f"{T.dir_parent}ctx{T.R} {ctx_bar}")
        return SEP_LIMITS.join(bars)

    def vibes_label(u7: float, r7: str) -> str:
        return _7d_pace_label(u7, r7)

    def combined(path: str, git: str, limits: str, vibes: str) -> str:
        return SEP_EXTRA.join(p for p in [path, git, limits, vibes] if p)

    now = datetime.now(timezone.utc)
    r5h = (now + timedelta(hours=4, minutes=26)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    r5h_low = (now + timedelta(minutes=23)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    r7d = (now + timedelta(days=4, hours=17)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    r7d_med = (now + timedelta(days=1, hours=5)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    r7d_crit = (now + timedelta(days=2, hours=4)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    gsd_line = f"⬆ /gsd:update {T.sep}│{T.R} Fixing auth bug {T.sep}│{T.R} █████░░░░░ 52%"

    pp = path_part()

    print("\n=== Demo: limits green — both windows low ===\n")
    print(combined(
        pp,
        git_line(DEMO_BRANCH_MAIN, f"{T.git_staged}+{T.R}", "",
                 f"{T.st_ok}{D}{D}{D}{T.R}"),
        limits_bars(12, r5h, 35, r7d, 24),
        vibes_label(35, r7d),
    ))

    print("\n=== Demo: limits yellow — 5h warn ===\n")
    print(combined(
        pp,
        git_line(DEMO_BRANCH_FEATURE, f"{T.git_dirty}*{T.R}{T.git_staged}+{T.R}",
                 f"{T.st_fail}CI{T.R}",
                 f"{T.st_fail}{D}{T.R}{T.st_wait}{D}{D}{T.R}{T.st_ok}{D}{D}{T.R}{T.st_none}{D}{T.R} {T.notif}💬2{T.R}"),
        limits_bars(70, r5h, 45, r7d, 65),
        vibes_label(45, r7d),
    ))

    print("\n=== Demo: 5h exhausted (red), 7d for context ===\n")
    print(combined(
        pp,
        git_line(DEMO_BRANCH_FEATURE, f"{T.git_dirty}*{T.R}",
                 f"{T.st_wait}CI{T.R}",
                 f"{T.st_wait}{D}{T.R}{T.st_ok}{D}{D}{T.R}"),
        limits_bars(100, r5h_low, 80, r7d_med, 80),
        vibes_label(80, r7d_med),
    ))

    print("\n=== Demo: 7d exhausted — only 7d shown ===\n")
    print(combined(
        pp,
        git_line(DEMO_BRANCH_DEV, f"{T.git_ahead}↑{T.R}"),
        limits_bars(100, r5h_low, 100, r7d_crit, 45),
        vibes_label(100, r7d_crit),
    ))

    print("\n=== Demo: 2-line with GSD slot ===\n")
    print(render([
        combined(
            pp,
            git_line(DEMO_BRANCH_FEATURE, f"{T.git_dirty}*{T.R}{T.git_staged}+{T.R}",
                     f"{T.st_fail}CI{T.R}",
                     f"{T.st_fail}{D}{T.R}{T.st_wait}{D}{D}{T.R}{T.st_ok}{D}{D}{T.R}{T.st_none}{D}{T.R} {T.notif}💬3{T.R}"),
            limits_bars(25, r5h, 18, r7d, 30),
            vibes_label(18, r7d),
        ),
        gsd_line,
    ]))

    print("\n=== Demo: gh not installed ===\n")
    print(combined(
        pp,
        git_line(DEMO_BRANCH_MAIN, "", "", f"{T.err}gh not installed{T.R}"),
        limits_bars(5, r5h, 10, r7d, 8),
        vibes_label(10, r7d),
    ))

    print("\n=== Color ramp presets ===\n")
    for name, wp in RAMP_PRESETS.items():
        vbars = ""
        for p in range(0, 101, 5):
            vbars += _vbar(p, ramp=wp)
        print(f"  {name:10s} {vbars}")
        print()


# --- install -----------------------------------------------------------------

SETTINGS_FILE = Path.home() / ".claude" / "settings.json"


def install() -> None:
    """Write this script as statusLine command in ~/.claude/settings.json."""
    script_path = str(Path(__file__).resolve())
    command = f"{sys.executable} {script_path}"

    settings: dict = {}
    if SETTINGS_FILE.exists():
        try:
            settings = json.loads(SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    old = settings.get("statusLine", {}).get("command", "")
    settings["statusLine"] = {"type": "command", "command": command}

    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2) + "\n")

    if old and old != command:
        print(f"Replaced: {old}")
    print(f"Installed: {command}")
    print(f"Config:    {SETTINGS_FILE}")


# --- main (dispatch) --------------------------------------------------------

def editor_main() -> None:
    """TUI theme editor mode."""
    _load_validated_config()
    if not sys.stdin.isatty():
        print("Error: theme editor requires an interactive terminal", file=sys.stderr)
        sys.exit(1)
    Editor().run()


def _ensure_cache_dirs() -> None:
    """Create all cache directories once at startup."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SLOT_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def statusline_main() -> None:
    """Normal statusline mode: read stdin JSON, execute slots, output lines."""
    slots = _load_theme_config()
    _ensure_cache_dirs()

    def _stdin_timeout(signum, frame):
        raise TimeoutError
    old_handler = signal.signal(signal.SIGALRM, _stdin_timeout)
    try:
        signal.alarm(1)
        raw = sys.stdin.read()
    except TimeoutError:
        print("FATAL: Timed out reading stdin", file=sys.stderr)
        sys.exit(1)
    except (OSError, IOError, BrokenPipeError) as e:
        print(f"FATAL: Failed to read stdin: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        signal.alarm(0)
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


def _print_help() -> None:
    print(f"""omcc-statusline — Claude Code statusline + theme editor

Usage:
  <stdin JSON> | omcc-statusline.py   Statusline mode (default)
  omcc-statusline.py --theme          TUI theme editor
  omcc-statusline.py --demo           Print demo scenarios
  omcc-statusline.py --install        Register in ~/.claude/settings.json
  omcc-statusline.py --help           Show this help

Theme editor is also activated when invoked via a symlink
containing "theme" in its name (e.g. theme-editor.py).

Config: {CONFIG_FILE}""")


def main() -> None:
    name = Path(sys.argv[0]).stem
    if "theme" in name:
        editor_main()
    elif len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        _print_help()
    elif len(sys.argv) > 1 and sys.argv[1] == "--theme":
        editor_main()
    elif len(sys.argv) > 1 and sys.argv[1] == "--install":
        install()
    elif len(sys.argv) > 1 and sys.argv[1] == "--demo":
        _load_theme_config()
        demo()
    else:
        statusline_main()


if __name__ == "__main__":
    main()
