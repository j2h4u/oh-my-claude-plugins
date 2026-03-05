# omcc-statusline

## What This Is

A single-file Python statusline for Claude Code CLI (~2600 lines) providing real-time display of git status, GitHub CI/PR state, API rate limits, context window usage, and external slot output. Includes a built-in TUI theme editor with 256-color picker.

## Core Value

Render accurate, themeable status information in Claude Code's statusline with minimal latency per prompt render.

## Requirements

### Validated

- Statusline renders path, git, CI/PR, limits, context, vibes, external slots
- SQLite-based cache with background subprocess refresh (fire-and-forget)
- TUI theme editor with live preview and 256-color grid
- Configurable slots, separators, ramp presets, display modes
- Semantic color tokens: ok, warn, err, wait, none
- OAuth token reading from Claude credentials
- Cooldown/retry handling for API rate limits

### Active

- [ ] Remove dead code and unused parameters
- [ ] Optimize SQLite connection lifecycle (singleton vs open-per-call)
- [ ] Consolidate duplicated config loading paths
- [ ] Extract DRY helpers for repeated patterns
- [ ] Structural improvements (return structured data from providers)

### Out of Scope

- Multi-file refactor (splitting into modules) -- single-file constraint intentional for plugin distribution
- Editor class decomposition -- works well enough, complexity justified by feature set
- Exotic ANSI attribute removal -- kept for theme editor completeness

## Context

Seven parallel code review agents (SOLID, DRY, YAGNI, KISS + Kaizen reuse/quality/efficiency) analyzed the codebase and produced prioritized findings. All findings validated with line numbers. Key themes:

- **Dead code**: 5 clear-cut items (unused functions, constants, parameters)
- **SQLite overhead**: ~15-20 DB open/close/PRAGMA/DDL cycles per render, reducible to 1
- **DRY violations**: duplicated config loading, repeated placeholder patterns, verbose INDICATOR_CONFIG pass-through
- **Structural**: ANSI regex for PR stripping, synchronous CI fetch blocking up to 15s

## Constraints

- **Single file**: Plugin distribution requires single `omcc-statusline.py`
- **Startup latency**: Runs on every prompt render -- must be fast
- **Backward compat**: User configs (`~/.config/omcc-statusline/config.json`) must continue working
- **Background subprocesses**: `_BG_SCRIPT` code generation is a conscious trade-off for fire-and-forget isolation

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Single-file architecture | Plugin marketplace requires self-contained distribution | -- Pending |
| SQLite WAL for cache | Concurrent read/write from main + background processes | Good |
| Fire-and-forget subprocesses | Never block render for API/git calls | Good |
| Semantic color tokens (ok/warn/err) | Unified theming, fewer tokens to configure | Good |

## Current Milestone: v1.0 Code Quality

**Goal:** Improve code quality, eliminate dead code, optimize hot-path performance, and consolidate DRY violations based on 7-agent review findings.

**Target features:**
- Dead code removal (zero risk)
- SQLite connection optimization (biggest perf win)
- DRY helper extraction
- Structural provider improvements

---
*Last updated: 2025-07-14 after 7-agent code review*
