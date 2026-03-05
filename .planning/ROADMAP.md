# Roadmap: omcc-statusline v1.0 Code Quality

## Overview

Improve code quality of omcc-statusline.py based on 7-agent review findings. Work progresses from zero-risk dead code removal through performance optimization (SQLite singleton), then DRY consolidation (split into core runtime helpers and editor-specific helpers), finishing with structural provider improvements that benefit from the cleaner codebase. All changes target a single file: `meta/utils/statusline/omcc-statusline.py`.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Dead Code Removal** - Remove unused functions, constants, and parameters identified by review agents
- [ ] **Phase 2: SQLite Connection Optimization** - Replace per-call DB opens with singleton connection for render-path performance
- [ ] **Phase 3: DRY Core Helpers** - Extract reusable helpers for cache access, config loading, settings defaults, and indicator rendering
- [ ] **Phase 4: DRY Editor Helpers** - Extract reusable helpers for theme entry construction, separator display, preview building, and color blocks
- [ ] **Phase 5: Structural Improvements** - Refactor providers to return structured data, flatten conditionals, and separate concerns

## Phase Details

### Phase 1: Dead Code Removal
**Goal**: Codebase contains only code that is actively used
**Depends on**: Nothing (first phase)
**Requirements**: DEAD-01, DEAD-02, DEAD-03, DEAD-04
**Success Criteria** (what must be TRUE):
  1. `grep -n "def ul_color" omcc-statusline.py` returns no matches
  2. `grep -n "STDERR_MAX_LEN" omcc-statusline.py` returns no matches
  3. `provider_path` signature has no `input_json` parameter; callers unchanged
  4. `provider_vibes` signature has no `cwd` or `show` parameters; callers unchanged
  5. Statusline renders identically before and after (no behavior change)
**Plans**: 1 plan

Plans:
- [x] 01-01-PLAN.md — Remove all dead code items (ul_color, STDERR_MAX_LEN, unused provider params)

### Phase 2: SQLite Connection Optimization
**Goal**: Database opens once per process lifetime instead of per-call, eliminating redundant PRAGMA/DDL overhead on every render
**Depends on**: Phase 1
**Requirements**: SQL-01, SQL-02, SQL-03
**Success Criteria** (what must be TRUE):
  1. A single `sqlite3.connect()` call serves all cache reads/writes within one process invocation
  2. PRAGMA statements (journal_mode, synchronous) and CREATE TABLE execute exactly once at connection init
  3. Background subprocesses create their own independent connection (no shared state across process boundary)
  4. Statusline renders identically before and after (cache hit/miss behavior unchanged)
**Plans**: 1 plan

Plans:
- [x] 02-01-PLAN.md — Implement singleton connection with init-time PRAGMA/DDL and subprocess isolation

### Phase 3: DRY Core Helpers
**Goal**: Repeated patterns in the runtime statusline path are consolidated into named helpers with single call sites replacing duplicated logic
**Depends on**: Phase 2 (cache helpers DRY-01 depend on new singleton connection API)
**Requirements**: DRY-01, DRY-02, DRY-03, DRY-04, DRY-05, DRY-06, DRY-07
**Success Criteria** (what must be TRUE):
  1. Cache access uses named helpers (`cache_get_raw`, `updated_at`, `cooldown`) instead of raw tuple unpacking at 8+ sites
  2. JSON file loading goes through `_load_json_file()` at all 4 config/credentials sites
  3. Settings retrieval uses `_get_setting()` with auto-fallback at all 6 sites instead of inline `dict.get(..., default)` chains
  4. Indicator formatting uses `_format_limit_window_for_prefix()` and `_render_indicator_for_prefix()` instead of duplicated lookup+format code
  5. Statusline renders identically before and after (no behavior change)
**Plans**: TBD

Plans:
- [ ] 03-01: Extract cache access and JSON/config helpers (DRY-01, DRY-02, DRY-03, DRY-04, DRY-07)
- [ ] 03-02: Extract indicator rendering helpers (DRY-05, DRY-06)

### Phase 4: DRY Editor Helpers
**Goal**: Repeated patterns in the theme editor TUI are consolidated into named helpers
**Depends on**: Phase 3 (DRY-09 separator helper depends on DRY-03 separator loading helper)
**Requirements**: DRY-08, DRY-09, DRY-10, DRY-11, DRY-12
**Success Criteria** (what must be TRUE):
  1. ThemeEntry construction uses `ThemeEntry.from_dict()` classmethod at all 4 construction sites
  2. ThemeEntry attribute copying uses `ThemeEntry.copy()` consistently at all 4 sites
  3. Preview parts building uses a shared helper instead of duplicated assembly at 5 sites
  4. Color block rendering uses a shared helper instead of duplicated grid logic at 5 sites
  5. Theme editor TUI behavior is identical before and after (preview, color picker, save all work unchanged)
**Plans**: TBD

Plans:
- [ ] 04-01: Extract ThemeEntry helpers (DRY-08, DRY-12)
- [ ] 04-02: Extract editor display helpers (DRY-09, DRY-10, DRY-11)

### Phase 5: Structural Improvements
**Goal**: Providers return structured data instead of pre-formatted strings, conditionals are flattened, and mixed concerns are separated
**Depends on**: Phase 4 (cleaner codebase makes structural changes safer)
**Requirements**: STR-01, STR-02, STR-03, STR-04
**Success Criteria** (what must be TRUE):
  1. `get_pr_status()` returns structured data (counts/states) and ANSI regex stripping is eliminated from callers
  2. `provider_limits()` uses early returns instead of nested if/else chains
  3. `execute_slots()` has separated concerns: grid layout logic is distinct from threading and error handling
  4. Theme serialization logic is shared between `save_theme()` and `_settings_from_config()` instead of duplicated
**Plans**: TBD

Plans:
- [ ] 05-01: Refactor get_pr_status to return structured data (STR-01)
- [ ] 05-02: Flatten provider_limits, separate execute_slots concerns, extract save_theme serialization (STR-02, STR-03, STR-04)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Dead Code Removal | 0/1 | Not started | - |
| 2. SQLite Connection Optimization | 0/1 | Not started | - |
| 3. DRY Core Helpers | 0/2 | Not started | - |
| 4. DRY Editor Helpers | 0/2 | Not started | - |
| 5. Structural Improvements | 0/2 | Not started | - |
