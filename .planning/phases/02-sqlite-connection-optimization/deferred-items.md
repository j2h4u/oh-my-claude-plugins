# Deferred Items - Phase 02

## Pre-existing Bug from Phase 01

**provider_path() and provider_vibes() keyword argument mismatch**

Phase 01 renamed unused `show` parameter to `_show` (underscore-prefix convention) in `provider_path()` (line 1323) and `provider_vibes()` (line 1309), but the caller `_run_slot()` (line 1473) passes `show=slot.get("show")` as a keyword argument. Since `_show` is keyword-only (after `*`), this causes a TypeError at runtime for any slot using these providers.

**Impact:** Statusline crashes when rendering slots that use `provider_path` or `provider_vibes` providers.

**Fix:** Either revert the underscore prefix on `show` parameter for these two providers, or change them to accept `**kwargs` / use positional convention matching the caller.

**Discovered during:** Phase 02 Plan 01, Task 2 (live render verification)
