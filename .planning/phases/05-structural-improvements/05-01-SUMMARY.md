---
phase: 05-structural-improvements
plan: 01
subsystem: statusline
tags: [refactoring, namedtuple, structured-data, ansi-regex-elimination, python]

requires:
  - phase: 04-dry-editor-helpers
    provides: editor display helpers extracted
provides:
  - PrStatus NamedTuple returning structured dot counts and unread count
  - _format_pr_dots helper formatting from structured data with include_pr/include_notif flags
  - Eliminated ANSI regex stripping (re.sub/re.search on escape sequences) from provider_git
affects: []

tech-stack:
  added: []
  patterns: [NamedTuple for structured return values, caller-controlled formatting from data]

key-files:
  created: []
  modified: [meta/utils/statusline/omcc-statusline.py]

key-decisions:
  - "get_pr_status returns None for all error/empty cases instead of inline error messages -- gh errors were a minor bug when shown even with show: [branch] only"
  - "PrStatus placed after ThemeEntry in data structures section, using typing.NamedTuple"

patterns-established:
  - "Structured return pattern: functions return typed data structures, callers format what they need instead of parsing pre-formatted output"

requirements-completed: [STR-01]

duration: 4min
completed: 2026-03-05
---

# Phase 5 Plan 1: PR Status Structured Data Summary

**Refactored get_pr_status to return PrStatus NamedTuple with dot counts by CI state and unread count, eliminating two ANSI regex operations from provider_git**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-05T18:06:18Z
- **Completed:** 2026-03-05T18:10:26Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- get_pr_status now returns PrStatus NamedTuple (or None) instead of pre-formatted ANSI string
- _format_pr_dots helper accepts include_pr/include_notif flags for caller-controlled formatting
- Removed re.sub and re.search on ANSI escape sequences from provider_git
- Plugin version bumped 1.0.53->1.0.54, marketplace synced

## Task Commits

Code changes were bundled with plan 05-02 execution (both plans modified the same file):

1. **Task 1: Return structured data from get_pr_status and format in provider_git** - `f25d13f` (refactor, bundled with 05-02 task 1)
2. **Task 2: Bump plugin version and sync marketplace** - `fbf7d6d` (chore, shared version bump with 05-02)

## Files Created/Modified
- `meta/utils/statusline/omcc-statusline.py` - PrStatus NamedTuple, structured get_pr_status, _format_pr_dots helper, updated provider_git
- `meta/.claude-plugin/plugin.json` - Version 1.0.53 -> 1.0.54
- `.claude-plugin/marketplace.json` - Version synced via build-marketplace.py

## Decisions Made
- get_pr_status returns None for error/empty cases (no-gh, no-auth, no cache, no nodes) instead of embedding error messages in the return value. This fixes a minor bug where gh error messages appeared even when user configured `show: ["branch"]` only.
- PrStatus NamedTuple uses string-quoted forward reference for return type annotation since the class is defined after function definitions it references.

## Deviations from Plan

None - plan executed exactly as written. Code was already committed as part of plan 05-02 execution which bundled both plans' changes into a single session.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- STR-01 complete: PR status returns structured data
- Combined with STR-02/03/04 from plan 05-02, all structural improvement requirements are addressed
- Phase 05 (and the entire v1.0 code quality milestone) is complete

---
*Phase: 05-structural-improvements*
*Completed: 2026-03-05*

## Self-Check: PASSED
