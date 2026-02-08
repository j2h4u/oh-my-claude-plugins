#!/usr/bin/env python3
"""TUI theme editor for Claude Code statusline.

Run: python3 theme-editor.py
Config: ~/.config/claude-statusline/theme.json
"""

import json
import os
import select
import sys
import tempfile
import termios
import tty
from dataclasses import dataclass, field
from pathlib import Path

# --- paths -------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".config" / "omcc-statusline"
CONFIG_FILE = CONFIG_DIR / "theme.json"

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

# --- element definitions ----------------------------------------------------

@dataclass
class ElementDef:
    key: str        # theme token name
    label: str      # short name for legend
    desc: str       # role description
    sample: str     # preview text
    group: str      # visual group id

ELEMENTS = [
    ElementDef("dir_parent",    "Parent dir",     "Muted parent directory in path",     "j2h4u/",   "dir"),
    ElementDef("dir_name",      "Current dir",    "Current working directory name",     "openclaw/","dir"),
    ElementDef("branch_sign",   "Branch sign",    "Git branch indicator symbol",        "⑂",        "git"),
    ElementDef("branch_name",   "Branch name",    "Current git branch name",            "main",     "git"),
    ElementDef("git_dirty",     "Dirty",          "Unstaged changes indicator",         "*",        "git"),
    ElementDef("git_staged",    "Staged",         "Staged changes indicator",           "+",        "git"),
    ElementDef("git_untracked", "Untracked",      "Untracked files indicator",          "?",        "git"),
    ElementDef("git_ahead",     "Ahead",          "Commits ahead of remote",            "↑",        "git"),
    ElementDef("git_behind",    "Behind",         "Commits behind remote",              "↓",        "git"),
    ElementDef("ci_ok",         "CI pass",        "CI checks passed (green)",           "CI",       "ci"),
    ElementDef("ci_fail",       "CI fail",        "CI checks failed (red)",             "CI",       "ci"),
    ElementDef("ci_wait",       "CI pending",     "CI checks running (blue)",           "CI",       "ci"),
    ElementDef("sep",           "Separator",      "Section separator",                  "|",        "ui"),
    ElementDef("pr_fail",       "PR fail",        "PR dot — failing CI",                "⁕",        "pr"),
    ElementDef("pr_wait",       "PR pending",     "PR dot — pending CI",                "⁕",       "pr"),
    ElementDef("pr_ok",         "PR pass",        "PR dot — passing CI",                "⁕",       "pr"),
    ElementDef("pr_none",       "PR unknown",     "PR dot — no CI status",              "⁕",        "pr"),
    ElementDef("notif",         "Notifications",  "Unread notification count",          "💬3",      "pr"),
    ElementDef("err",           "Error",          "Error messages",                     "error",    "ui"),
]

# --- theme data --------------------------------------------------------------

@dataclass
class ThemeEntry:
    fg: int | None = None          # 0-255 or None for terminal default
    bg: int | None = None          # 0-255 or None for transparent
    attrs: list[str] = field(default_factory=list)

DEFAULTS: dict[str, ThemeEntry] = {
    "dir_parent":     ThemeEntry(fg=239),
    "dir_name":       ThemeEntry(fg=238),
    "branch_sign":    ThemeEntry(fg=238),
    "branch_name":    ThemeEntry(fg=238),
    "git_dirty":      ThemeEntry(fg=3, attrs=["dim"]),
    "git_staged":     ThemeEntry(fg=2, attrs=["dim"]),
    "git_untracked":  ThemeEntry(fg=235),
    "git_ahead":      ThemeEntry(fg=6),
    "git_behind":     ThemeEntry(fg=5),
    "ci_ok":          ThemeEntry(fg=2),
    "ci_fail":        ThemeEntry(fg=1),
    "ci_wait":        ThemeEntry(fg=4),
    "pr_ok":          ThemeEntry(fg=2),
    "pr_fail":        ThemeEntry(fg=1),
    "pr_wait":        ThemeEntry(fg=4),
    "pr_none":        ThemeEntry(fg=8),
    "notif":          ThemeEntry(fg=6),
    "sep":            ThemeEntry(fg=8),
    "err":            ThemeEntry(fg=1),
}

# --- config I/O --------------------------------------------------------------

def load_theme() -> dict[str, ThemeEntry]:
    theme = {k: ThemeEntry(fg=v.fg, bg=v.bg, attrs=list(v.attrs))
             for k, v in DEFAULTS.items()}
    if CONFIG_FILE.exists():
        try:
            for key, val in json.loads(CONFIG_FILE.read_text()).items():
                if key in theme:
                    theme[key] = ThemeEntry(
                        fg=val.get("fg"), bg=val.get("bg"),
                        attrs=val.get("attrs", []),
                    )
        except (json.JSONDecodeError, OSError):
            pass
    return theme


def save_theme(theme: dict[str, ThemeEntry]) -> str:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    for key, entry in theme.items():
        d: dict = {}
        if entry.fg is not None:
            d["fg"] = entry.fg
        if entry.bg is not None:
            d["bg"] = entry.bg
        if entry.attrs:
            d["attrs"] = entry.attrs
        data[key] = d
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

# --- style builder -----------------------------------------------------------

def build_style(entry: ThemeEntry, extra: str = "") -> str:
    """Build ANSI escape string from a ThemeEntry."""
    parts: list[str] = []
    for attr in entry.attrs:
        if attr in ATTR_SGR:
            parts.append(ATTR_SGR[attr])
    if entry.fg is not None:
        parts.append(fg256(entry.fg))
    if entry.bg is not None:
        parts.append(bg256(entry.bg))
    if extra:
        parts.append(extra)
    return "".join(parts)

# --- TUI ---------------------------------------------------------------------

class Editor:
    def __init__(self):
        self.theme = load_theme()
        self.cursor = 0          # element index
        self.clipboard: ThemeEntry | None = None
        self.mode = "nav"        # nav | fg | bg | attr
        self.color_cursor = 0    # color picker position (0-255)
        self.attr_cursor = 0     # attribute picker position
        self.msg = ""
        self.running = True

    # --- preview rendering ---

    def _styled(self, key: str, text: str) -> str:
        entry = self.theme[key]
        # live preview: show tentative change while picking
        if key == ELEMENTS[self.cursor].key:
            if self.mode in ("fg", "bg"):
                entry = ThemeEntry(fg=entry.fg, bg=entry.bg, attrs=list(entry.attrs))
                if self.mode == "fg":
                    entry.fg = self.color_cursor if self.color_cursor >= 0 else None
                else:
                    entry.bg = self.color_cursor if self.color_cursor >= 0 else None
            elif self.mode == "attr":
                # show what toggling the hovered attribute would look like
                attr_name = ATTRS_AVAILABLE[self.attr_cursor][0]
                entry = ThemeEntry(fg=entry.fg, bg=entry.bg, attrs=list(entry.attrs))
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
        """Visible character count (emoji = 2 columns)."""
        import unicodedata
        n = 0
        for ch in text:
            if unicodedata.east_asian_width(ch) in ("W", "F"):
                n += 2
            else:
                n += 1
        return n

    def render_preview(self) -> tuple[str, str]:
        cur = ELEMENTS[self.cursor].key

        # (key_or_None, visible_text) — None means plain separator
        segments: list[tuple[str | None, str]] = [
            ("dir_parent", "j2h4u/"), ("dir_name", "openclaw/"),
            (None, " "),
            ("branch_sign", "⑂"), ("branch_name", "main"),
            ("git_dirty", "*"), ("git_staged", "+"),
            ("git_untracked", "?"),
            ("git_ahead", "↑"), ("git_behind", "↓"),
            (None, " "),
            ("ci_ok", "CI"), (None, " "), ("ci_fail", "CI"), (None, " "), ("ci_wait", "CI"),
            (None, " "),
            ("sep", "|"),
            (None, " "),
            ("pr_fail", "⁕"), ("pr_wait", "⁕"),
            ("pr_ok", "⁕"), ("pr_none", "⁕"),
            (None, " "),
            ("notif", "💬3"),
            (None, "  "),
            ("err", "error"),
        ]

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

        preview = "".join(preview_parts)
        carets = f"{DIM}{''.join(caret_chars)}{RESET}"
        return preview, carets

    # --- legend ---

    def render_legend(self) -> list[str]:
        elem = ELEMENTS[self.cursor]
        entry = self.theme[elem.key]

        fg_s = f"{fg256(entry.fg)}██{RESET} {entry.fg}" if entry.fg is not None else f"{DIM}default{RESET}"
        bg_s = f"{bg256(entry.bg)}  {RESET} {entry.bg}" if entry.bg is not None else f"{DIM}default{RESET}"
        attr_s = ", ".join(entry.attrs) if entry.attrs else f"{DIM}none{RESET}"

        return [
            f"{BOLD}{elem.label}{RESET}  {DIM}({elem.key}){RESET}  {DIM}{elem.desc}{RESET}",
            "",
            f"FG: {fg_s}   BG: {bg_s}   Attrs: {attr_s}",
        ]

    # --- color picker ---

    def render_color_grid(self, is_bg: bool) -> list[str]:
        lines: list[str] = []
        sel = self.color_cursor
        entry = self.theme[ELEMENTS[self.cursor].key]
        active = entry.bg if is_bg else entry.fg  # currently set color

        # fg cells: show element's bg + colored "xx" text
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

        # default option
        is_default = active is None
        dflt_arrow = f"{BLINK}{REVERSE}▸{RESET}" if sel == -1 else " "
        dflt_mark = f"{BOLD}●{RESET}" if is_default else f"{DIM}○{RESET}"
        lines.append(f"  {dflt_arrow} {dflt_mark} default {DIM}(transparent){RESET}")
        lines.append("")

        # row 0: basic 0-7
        lines.append("  " + " ".join(cell(i) for i in range(8)))
        # row 1: bright 8-15
        lines.append("  " + " ".join(cell(i) for i in range(8, 16)))
        lines.append("")

        # RGB cube: 6 rows, each row = 6 blocks of 6 (r varies across blocks, g is row, b is column)
        for g in range(6):
            row_cells = []
            for r in range(6):
                for b in range(6):
                    row_cells.append(cell(16 + 36 * r + 6 * g + b))
                if r < 5:
                    row_cells.append(" ")
            lines.append("  " + "".join(row_cells))
        lines.append("")

        # grayscale
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
                active = f"{BOLD}●{RESET}" if not entry.attrs else f"{DIM}○{RESET}"
                lines.append(f"  {arrow} {active} {color}{desc}{RESET}")
            else:
                active = f"{BOLD}●{RESET}" if name in entry.attrs else f"{DIM}○{RESET}"
                lines.append(f"  {arrow} {active} {color}{sgr}{desc}{RESET}")
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

        # tentative value preview — aligned under the relevant legend field
        if self.mode in ("fg", "bg", "attr"):
            entry = self.theme[ELEMENTS[self.cursor].key]
            fg_vis = (3 + len(str(entry.fg))) if entry.fg is not None else 7  # "██ N" or "default"
            bg_vis = (3 + len(str(entry.bg))) if entry.bg is not None else 7  # "   N" or "default"
            if self.mode == "fg":
                pad = 4  # "FG: "
                sel = self.color_cursor
                hint = f"{fg256(sel)}██{RESET} {sel}" if sel >= 0 else f"{DIM}default{RESET}"
            elif self.mode == "bg":
                pad = 4 + fg_vis + 3 + 4  # "FG: " + fg_s + "   " + "BG: "
                sel = self.color_cursor
                hint = f"{bg256(sel)}  {RESET} {sel}" if sel >= 0 else f"{DIM}default{RESET}"
            else:  # attr
                pad = 4 + fg_vis + 3 + 4 + bg_vis + 3 + 7  # ... + "   " + "Attrs: "
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

        out.append("\r\n")
        if self.mode == "nav":
            K = f"{RESET}\033[97m"  # bright white keys
            D = f"{RESET}"             # default descriptions
            out.append(f"  {D}← → navigate   {K}f{D} fg   {K}b{D} bg   {K}a{D} attrs   {K}c{D} copy   {K}v{D} paste   {K}s{D} save   {K}r{D} reset   {K}q{D} quit{RESET}\r\n")

        if self.msg:
            out.append(f"\r\n  {self.msg}\r\n")

        sys.stdout.write("".join(out))
        sys.stdout.flush()

    # --- key handling ---

    def handle_key(self, key: str):
        key = _CYRILLIC_MAP.get(key, key)
        self.msg = ""

        if self.mode == "nav":
            self._handle_nav(key)
        elif self.mode in ("fg", "bg"):
            self._handle_color(key)
        elif self.mode == "attr":
            self._handle_attr(key)

    def _handle_nav(self, key: str):
        if key == "q":
            self.running = False
        elif key == LEFT:
            self.cursor = (self.cursor - 1) % len(ELEMENTS)
        elif key == RIGHT:
            self.cursor = (self.cursor + 1) % len(ELEMENTS)
        elif key == "f":
            self.mode = "fg"
            e = self.theme[ELEMENTS[self.cursor].key]
            self.color_cursor = e.fg if e.fg is not None else -1
        elif key == "b":
            self.mode = "bg"
            e = self.theme[ELEMENTS[self.cursor].key]
            self.color_cursor = e.bg if e.bg is not None else -1
        elif key == "a":
            self.mode = "attr"
            self.attr_cursor = 0
        elif key == "s":
            path = save_theme(self.theme)
            self.msg = f"Saved → {path}"
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
            self.clipboard = ThemeEntry(fg=e.fg, bg=e.bg, attrs=list(e.attrs))
            self.msg = f"Copied {ELEMENTS[self.cursor].label}"
        elif key == "v":
            if self.clipboard:
                k = ELEMENTS[self.cursor].key
                self.theme[k] = ThemeEntry(
                    fg=self.clipboard.fg, bg=self.clipboard.bg,
                    attrs=list(self.clipboard.attrs))
                self.msg = f"Pasted → {ELEMENTS[self.cursor].label}"
            else:
                self.msg = "Nothing to paste"

    def _handle_color(self, key: str):
        if key == ESC_KEY:
            self.mode = "nav"
        elif self.color_cursor == -1:
            # on "default" row
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
                # from top row (basic 0-7) → go to default
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

    # --- terminal I/O ---

    def read_key(self) -> str:
        fd = sys.stdin.fileno()
        ch = os.read(fd, 1)
        if ch == b"\x1b":
            if select.select([fd], [], [], 0.1)[0]:
                ch2 = os.read(fd, 1)
                if ch2 == b"[":
                    ch3 = os.read(fd, 1)
                    # handle longer sequences like \x1b[1;5C
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
                    # application mode arrows: \x1bOA..D → map to CSI
                    ch3 = os.read(fd, 1)
                    return f"\x1b[{ch3.decode()}"
                return f"\x1b{ch2.decode()}"
            return ESC_KEY
        # multi-byte UTF-8: read remaining continuation bytes
        b0 = ch[0]
        if b0 >= 0xC0:
            need = (2 if b0 < 0xE0 else 3 if b0 < 0xF0 else 4) - 1
            ch += os.read(fd, need)
        return ch.decode()

    def run(self):
        old = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin)
            while self.running:
                self.render()
                key = self.read_key()
                self.handle_key(key)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
            sys.stdout.write(SHOW_CURSOR + CLEAR_SCREEN)
            sys.stdout.flush()


# --- grid navigation helper --------------------------------------------------

_GRID_ROWS: list[list[int]] = [
    list(range(0, 8)),       # basic
    list(range(8, 16)),      # bright
]
# RGB cube: visual rows match render order (g fixed per row, r×b left-to-right)
for _g in range(6):
    _row = []
    for _r in range(6):
        for _b in range(6):
            _row.append(16 + 36 * _r + 6 * _g + _b)
    _GRID_ROWS.append(_row)
_GRID_ROWS.append(list(range(232, 256)))  # grayscale
del _g, _r, _b, _row

# reverse lookup: color → (row, col)
_COLOR_POS: dict[int, tuple[int, int]] = {}
for _ri, _row in enumerate(_GRID_ROWS):
    for _ci, _color in enumerate(_row):
        _COLOR_POS[_color] = (_ri, _ci)
del _ri, _row, _ci, _color


def _row_visual_x(row_i: int) -> list[int]:
    """Compute visual x-position (left edge) for each cell in a grid row."""
    n = len(_GRID_ROWS[row_i])
    if n == 8:       # basic / bright: " ".join → 2ch cell + 1ch space
        return [c * 3 for c in range(n)]
    elif n == 36:    # RGB cube: 6 blocks of 6, space between blocks
        return [c * 2 + c // 6 for c in range(n)]
    else:            # grayscale (24): no spaces
        return [c * 2 for c in range(n)]


# precompute visual positions for all rows
_VISUAL_X: list[list[int]] = [_row_visual_x(i) for i in range(len(_GRID_ROWS))]


def _closest_col(row_i: int, target_x: int) -> int:
    """Find column in row_i whose visual x is closest to target_x."""
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
    """Move in the color grid. direction: 'up', 'down', 'left', 'right'."""
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
}


def main():
    if not sys.stdin.isatty():
        print("Error: theme editor requires an interactive terminal", file=sys.stderr)
        sys.exit(1)
    Editor().run()


if __name__ == "__main__":
    main()
