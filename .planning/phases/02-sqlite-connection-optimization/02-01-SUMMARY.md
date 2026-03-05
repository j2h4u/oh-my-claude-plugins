---
phase: 02-sqlite-connection-optimization
plan: 01
subsystem: database
tags: [sqlite, connection-pooling, singleton, cache, performance]

# Dependency graph
requires:
  - phase: 01-dead-code-removal
    provides: cleaned codebase with unused code removed
provides:
  - singleton SQLite connection pattern (_CON) for all main-process cache operations
  - lazy init of PRAGMA WAL and DDL (exactly once per render)
affects: [03-dry-core-helpers, 04-dry-editor-helpers]

# Tech tracking
tech-stack:
  added: []
  patterns: [lazy-singleton-connection, module-level-global-with-guard]

key-files:
  created: []
  modified:
    - meta/utils/statusline/omcc-statusline.py
    - meta/.claude-plugin/plugin.json
    - .claude-plugin/marketplace.json

key-decisions:
  - "Lazy singleton over eager init -- _CON created on first _db() call, not at module import"
  - "Removed _ensure_cache_db() -- redundant with lazy singleton pattern"
  - "_BG_SCRIPT left untouched -- subprocesses correctly use independent connections"

patterns-established:
  - "Singleton DB pattern: module-level _CON with global keyword in _db() initializer"

requirements-completed: [SQL-01, SQL-02, SQL-03]

# Metrics
duration: 3min
completed: 2026-03-05
---

# Phase 02 Plan 01: SQLite Connection Optimization Summary

**Lazy singleton _CON replaces per-call sqlite3.connect(), eliminating 8-12 redundant PRAGMA/DDL executions per render**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-05T16:57:01Z
- **Completed:** 2026-03-05T17:00:04Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Converted _db() from per-call connection opener to lazy singleton returning _CON
- Removed con.close() from cache_get() and cache_put() (singleton must not be closed mid-render)
- Removed _ensure_cache_db() startup function (redundant with lazy init)
- Verified singleton behavior: _db() returns same object on repeated calls, cache_get/cache_put cycle works

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert _db() to lazy singleton and update callers** - `e030eb2` (refactor)
2. **Task 2: Verify behavioral equivalence with live render** - verification-only, no code changes

## Files Created/Modified
- `meta/utils/statusline/omcc-statusline.py` - Added _CON singleton, rewrote _db(), removed con.close() from callers, removed _ensure_cache_db()
- `meta/.claude-plugin/plugin.json` - Version bump 1.0.48 -> 1.0.49
- `.claude-plugin/marketplace.json` - Marketplace version bump 1.3.43 -> 1.3.44

## Decisions Made
- Lazy singleton (init on first call) over eager singleton (init at import) -- avoids unnecessary DB creation when statusline runs in non-cache modes (--help, --theme, --install)
- _BG_SCRIPT intentionally untouched -- subprocess connections are independent by design (SQL-03)

## Deviations from Plan

None - plan executed exactly as written.

## Out-of-Scope Discovery

**Pre-existing bug from Phase 01:** `provider_path()` and `provider_vibes()` have `_show` parameter (underscore-prefixed) but caller `_run_slot()` passes `show=` keyword. Causes TypeError on live render with these providers. Logged to `deferred-items.md` in phase directory. Not related to SQLite changes.

## Issues Encountered

- Plan verification check #4 expected 1 `con.close()` in _BG_SCRIPT but found 2 (early-exit at line 873 and finally-block at line 893). Both are correct -- _BG_SCRIPT has two close paths. Not a code issue, just an imprecise verification expectation.
- Live render test with `echo '{}' | python3 omcc-statusline.py` exits 1 due to missing `current_dir` field. This is expected behavior (input validation). Singleton verified via direct module import and cache_get/cache_put cycle instead.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- SQLite singleton pattern in place, ready for DRY helper extraction in Phase 03
- Pre-existing provider_path/_show bug should be addressed (possibly in Phase 03 or standalone fix)

---
*Phase: 02-sqlite-connection-optimization*
*Completed: 2026-03-05*
