# Requirements: omcc-statusline

**Defined:** 2025-07-14
**Core Value:** Render accurate, themeable status information with minimal latency per prompt render

## v1 Requirements

Requirements for v1.0 Code Quality milestone. Each maps to roadmap phases.

### Dead Code

- [x] **DEAD-01**: Remove unused `ul_color` function (line 126)
- [x] **DEAD-02**: Remove unused `STDERR_MAX_LEN` constant (line 75)
- [x] **DEAD-03**: Remove unused `input_json` parameter from `provider_path`
- [x] **DEAD-04**: Remove unused `cwd`/`show` parameters from `provider_vibes`

### SQLite Optimization

- [x] **SQL-01**: Replace per-call `_db()` with singleton connection (eliminate 8-12 opens per render)
- [x] **SQL-02**: Run PRAGMA and DDL only once at connection init, not per call
- [x] **SQL-03**: Ensure singleton works safely with background subprocess isolation

### DRY Consolidation

- [ ] **DRY-01**: Extract `cache_get_raw/updated_at/cooldown` helpers to replace 8x tuple unpacking
- [ ] **DRY-02**: Consolidate config file loading into single `_load_json_file()` helper (4 sites)
- [ ] **DRY-03**: Extract `_load_separator()` helper for triple if/else pattern
- [ ] **DRY-04**: Extract `_get_setting()` with auto-fallback to `_SETTINGS_DEFAULTS` (6 sites)
- [ ] **DRY-05**: Extract `_format_limit_window_for_prefix()` to internalize INDICATOR_CONFIG lookup (4 sites)
- [ ] **DRY-06**: Extract `_render_indicator_for_prefix()` wrapper (3 sites)
- [ ] **DRY-07**: Extract `_safe_json_loads()` for JSON parse with error handling (3 sites)
- [ ] **DRY-08**: Add `ThemeEntry.from_dict()` classmethod for consistent construction (4 sites)
- [ ] **DRY-09**: Consolidate separator display mapping into helper (3 sites)
- [ ] **DRY-10**: Extract preview parts building helper for editor (5 sites)
- [ ] **DRY-11**: Consolidate color block building for editor (5 sites)
- [ ] **DRY-12**: Use `ThemeEntry.copy()` consistently for attribute copying (4 sites)

### Structural

- [ ] **STR-01**: Return structured data from `get_pr_status()` instead of formatted string (eliminate ANSI regex)
- [ ] **STR-02**: Flatten `provider_limits()` conditionals with early returns
- [ ] **STR-03**: Simplify `execute_slots()` mixed concerns (grid layout, threading, error handling)
- [ ] **STR-04**: Extract serialization logic from `save_theme()` to reduce duplication with `_settings_from_config()`

## Future Requirements

None currently deferred.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-file refactor (splitting into modules) | Single-file constraint intentional for plugin distribution |
| Editor class decomposition | Works well enough, complexity justified by feature set |
| Async I/O rewrite | Background subprocess model is deliberate design choice |
| Shell injection hardening (shell=True) | User-supplied slot commands are trusted config, not external input |
| Network I/O timeouts for git reads | Edge case (NFS mounts), not worth complexity |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEAD-01 | Phase 1 | Complete |
| DEAD-02 | Phase 1 | Complete |
| DEAD-03 | Phase 1 | Complete |
| DEAD-04 | Phase 1 | Complete |
| SQL-01 | Phase 2 | Complete |
| SQL-02 | Phase 2 | Complete |
| SQL-03 | Phase 2 | Complete |
| DRY-01 | Phase 3 | Pending |
| DRY-02 | Phase 3 | Pending |
| DRY-03 | Phase 3 | Pending |
| DRY-04 | Phase 3 | Pending |
| DRY-05 | Phase 3 | Pending |
| DRY-06 | Phase 3 | Pending |
| DRY-07 | Phase 3 | Pending |
| DRY-08 | Phase 4 | Pending |
| DRY-09 | Phase 4 | Pending |
| DRY-10 | Phase 4 | Pending |
| DRY-11 | Phase 4 | Pending |
| DRY-12 | Phase 4 | Pending |
| STR-01 | Phase 5 | Pending |
| STR-02 | Phase 5 | Pending |
| STR-03 | Phase 5 | Pending |
| STR-04 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0

---
*Requirements defined: 2025-07-14*
*Last updated: 2025-07-14 after roadmap creation*
