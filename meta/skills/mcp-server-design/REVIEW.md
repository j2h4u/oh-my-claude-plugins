# MCP Server Design Skill — Review Action Items

> Generated 2026-05-22 from a three-perspective subagent review (newcomer, pragmatic skeptic,
> cross-reference coherence auditor). Items grouped by severity. Check off as closed.
>
> **Path conventions in this file:** all paths are relative to
> `meta/skills/mcp-server-design/` unless absolute. Line numbers are point-in-time and may
> drift — confirm before editing.

---

## How to close items

- Group items by file and dispatch one subagent per file (avoid conflicting edits)
- Haiku for mechanical replacements; Sonnet for anything requiring judgment or prose rewriting
- After each fix: check the box `[x]` in this file and append a one-line note: *"closed YYYY-MM-DD: <what changed>"*
- Bump `meta/.claude-plugin/plugin.json` patch version + run `./scripts/build-marketplace.py --sync` after each commit (per repo CLAUDE.md)

---

## 🔴 Hard contradictions

### 1. Tool-count threshold inconsistent across 3 files
- [x] **Pick one canonical home (proposal: `tool-design.md`), make others reference it**
  - `SKILL.md:114` says "≤ 15 primary tools"
  - `references/tool-design.md:75` says "≤12 primary tools"
  - `references/design-philosophy.md:80` says "5–15 tools per server"
  - Also `design-philosophy.md:43` cites GitHub MCP "40 → 3–10" — empirical evidence actually argues for ≤5
  - **Fix:** state ONE number in `tool-design.md` framed as rule-of-thumb (not a benchmark); `SKILL.md` and `design-philosophy.md` reference it without restating a number
  - *closed 2026-05-22: tool-design.md now states "≤10 primary tools (rule of thumb)" with strong-bias-toward-fewer framing; SKILL.md and design-philosophy.md defer to it without restating a number; GitHub MCP anecdote retained as supporting evidence.*

### 2. snake_case / PascalCase cleanup incomplete
- [x] **Mass replace PascalCase tool name examples → snake_case** in:
  - `references/agent-ux.md` — `SearchMessages`, `MarkDialogForSync`, `GetEntityInfo`, `ListDialogs`, `SubmitFeedback`, `QueryX`, `SearchX`, `ListMessages`
  - `references/feedback-tool.md` — `SubmitFeedback` throughout the body
  - `references/clients.md` — `GetMe → GetMyAccount` example
  - Error-message examples in `references/tool-design.md` like `"use ListDialogs"` → `"use list_dialogs"`
  - Commit `8bb8a96` (Apr) established snake_case as primary; cleanup was incomplete
  - *closed 2026-05-22: snake_case applied across all skill files; cleanup pass also caught stragglers in SKILL.md, observability.md, audit-checklist.md, tool-design.md (SearchMessages, SubmitFeedback, GetTaskStatus, CheckJobResult, GetMyRecentActivity). Grep confirms no PascalCase tool-name references remain.*

### 3. stderr logging contradiction
- [x] **Reconcile stderr rule across SKILL.md, security.md, daemon-architecture.md**
  - `SKILL.md:155` + `references/security.md` — "all logging MUST go to stderr"
  - `references/daemon-architecture.md` — "Do NOT write stderr from MCP server, оно уходит к клиенту, не оператору"
  - **Fix:** in SKILL.md/security.md make rule conditional: "stderr unless your architecture splits logging via a daemon — see daemon-architecture.md". Reverse-link from daemon-architecture.md
  - *closed 2026-05-22: rule now conditional in SKILL.md (Transport section) and security-threats.md §0 — "stderr by default; daemon-split architectures override, see daemon-architecture.md". Reverse-link added in daemon-architecture.md.*

---

## 🟠 Structural — overlap and tag taxonomy

### 4. `security.md` and `security-threats.md` overlap ~80%
- [x] **Merge: `security.md` → `security-threats.md`, delete `security.md`**
  - Pragmatic reviewer #3 + Coherence reviewer #6 both flagged
  - Sections that overlap: prompt injection / localhost / Origin / input boundary
  - Plan: `security-threats.md` gets a new §0 "Basic Hygiene Baseline" (1-page summary, replacing what was in security.md), then deep sections continue as is
  - Update references in: `SKILL.md` (3 spots), `references/audit-checklist.md` (§14 cross-refs)
  - Delete `references/security.md`
  - *closed 2026-05-22: security.md deleted; security-threats.md gained §0 Basic Hygiene Baseline (prompt injection, localhost binding, Origin validation, annotation trust, input boundary, transport/stderr). SKILL.md cross-refs updated (3 spots); audit-checklist.md grep showed cross-refs already correct.*

### 5. `[CONDITIONAL]` tag used but not declared
- [x] **Add `CONDITIONAL` to scope-tag legend in `SKILL.md:22-34`**
  - Used heavily in `audit-checklist.md` and `daemon-architecture.md`
  - Definition (proposed): *"CONDITIONAL — applies when the named precondition holds (specific transport, deployment shape, or stack); skip otherwise."*
  - *closed 2026-05-22: CONDITIONAL added to SKILL.md scope-tag legend with the proposed definition.*

### 6. Tag syntax mismatch (`STACK-SPECIFIC` vs `[STACK:X]`)
- [x] **Unify to bracket form `[STACK:X]` everywhere**
  - SKILL.md uses prose: `*(STACK-SPECIFIC: stateful backends only)*`
  - `audit-checklist.md` uses brackets: `[STACK:Python]`, `[Claude Desktop, Claude Code ≥2.0.21]`
  - Pick brackets — shorter, easier to scan
  - *closed 2026-05-22: SKILL.md prose `*(STACK-SPECIFIC: ...)*` converted to bracket form ([STACK:stateful-backends], [STACK:remote-multi-server], [STACK:Python], [STACK:FastMCP]). Term "STACK-SPECIFIC" retained only in legend definition.*

### 7. Observability summary in `SKILL.md` too heavy
- [x] **Shrink `SKILL.md:183-200` to ≤6 lines + bullet list**
  - Currently restates ~70% of `observability.md`; breaks the summary+ref pattern used elsewhere
  - Keep: why, the 3 decisions it informs, minimum fields, "no raw args" rule, "see observability.md"
  - *closed 2026-05-22: observability section in SKILL.md shrunk from 16 lines to 6 — three decisions, minimum fields, no-raw-args rule, pointer to observability.md.*

---

## 🟡 Magic numbers — undefended thresholds

### 8a. `≤ 300 tokens` system prompt
- [x] **Soften in `SKILL.md:140` and `references/agent-ux.md:96`**
  - Keep the budget *principle*; remove the specific number or label it "rule of thumb"
  - *closed 2026-05-22: SKILL.md replaced `≤ 300 tokens` with "keep short (rule of thumb: a few hundred tokens)". agent-ux.md already used soft language ("Start minimal", "keep it tight") — no specific 300-token line was present to soften.*

### 8b. Dead-tool window: "30 days, ≥ 100 calls"
- [x] **Soften in `references/observability.md:116`**
  - Replace with principle-based wording: *"enough calls in the window for the median to be statistically meaningful"*
  - *closed 2026-05-22: replaced with principle-based wording — window length depends on call frequency (longer for cold tools, shorter for hot ones).*

### 8c. `p95 > 5s → async`
- [x] **Soften in `references/observability.md:159`**
  - "p95 exceeds the agent's wait tolerance for this tool's perceived cost"
  - *closed 2026-05-22: hard `p95 > 5s` replaced with "when p95 exceeds the agent's wait tolerance for this tool's perceived cost, return an async handle (job id) and a status tool."*

### 8d. Reporting cadence "monthly during MVP, quarterly after"
- [x] **Remove from `references/observability.md:111`** — cargo-cult, unjustified
  - *closed 2026-05-22: cadence parenthetical removed entirely; section heading is now plain `## Reports to run`.*

### 8e. `1 MiB request cap`
- [x] **Soften in `references/security-threats.md:196`**
  - "Tight enough that one request cannot OOM the process; servers accepting file uploads need higher caps"
  - *closed 2026-05-22: replaced with principle-based wording per proposed text.*

### 8f. `30s timeout` default
- [x] **Soften in `references/security-threats.md:193`**
  - "Hard upper bound proportional to the slowest *acceptable* response; ML-inference tools may need minutes"
  - *closed 2026-05-22: replaced with principle-based wording per proposed text.*

### 8g. `secrets.token_urlsafe(32)` clarification
- [x] **Annotate in `references/security-threats.md:149`**
  - Add inline: *"(32 bytes = 256 bits, well above the 128-bit floor)"*
  - *closed 2026-05-22: inline annotation added.*

### 8h. `security-threats.md §7` reads as generic security textbook
- [x] **Trim §7 to MCP-specific bullets only**
  - Drop or compress: branch protection, 2FA, signed releases, semver-as-such — these are general software hygiene
  - Keep MCP-specific: "claim your registry namespace early", "tool-surface stability via semver", "publish provenance so hosts can verify"
  - Add one-line pointer: *"see general supply-chain hygiene resources; below is the MCP-specific addition"*
  - *closed 2026-05-22: §7 trimmed to 3 MCP-specific bullets (namespace early, provenance publishing, tool-surface stability via semver) with pointer to general supply-chain hygiene resources.*

---

## 🟢 SubmitFeedback over-elevation

### 9. SubmitFeedback framed as universal default
- [x] **Tone down "strong default" language + add "When NOT to use" block**
  - Currently elevated in: `SKILL.md:113-128`, `feedback-tool.md`, `agent-ux.md:197-213`, `audit-checklist.md:102-107`, `observability.md:25`
  - Add to `feedback-tool.md`: short "When NOT to use" section listing: multi-tenant servers (privacy), adversarial environments (feedback is an injection surface), servers with no maintainer reviewing the queue, short-lived deployments
  - In `SKILL.md`: change "strong default" → "useful pattern when there's a maintainer who reads the queue"
  - *closed 2026-05-22: tone moderated across SKILL.md, feedback-tool.md, agent-ux.md, observability.md, audit-checklist.md to "useful pattern when there's a maintainer who reads the queue". feedback-tool.md gained a "When NOT to use" section (multi-tenant, adversarial, no-maintainer, short-lived). audit-checklist.md item demoted from required to conditional with N/A escape hatch.*

---

## 🟢 First-timer friction (newcomer reviewer)

### 10a. Scope tags introduced before defined
- [x] **In `SKILL.md`, place the tag legend before or alongside first usage**
  - Currently first-time reader hits `*(UNIVERSAL)*` etc. before the legend at line 22-34
  - *closed 2026-05-22: verified that the legend now precedes first scope-tag usage in SKILL.md (no structural move needed after the rewrite).*

### 10b. `structuredContent` jargon used without inline gloss
- [x] **`SKILL.md:109` — add 6-word gloss**
  - Definition lives at `tool-design.md:142-169`; readers shouldn't have to jump
  - *closed 2026-05-22: inline gloss added — "(MCP's typed return-value field, see tool-design.md)".*

### 10c. Daemon section reads as mandatory
- [x] **`SKILL.md:148-151` — add explicit "skip unless backend is stateful" sentence**
  - *closed 2026-05-22: daemon section heading carries [STACK:stateful-backends] tag and explicit skip sentence at top.*

### 10d. observability.md examples use Pattern B (SQL), Pattern A (JSONL) has no example
- [x] **Add one `jq` or DuckDB-on-JSONL example to `references/observability.md`**
  - Most first-timer servers will go Pattern A
  - *closed 2026-05-22: two Pattern A examples added — `jq`+`awk` pipeline for per-tool error rate, and DuckDB one-liner for p95 latency per tool, both reading directly from calls.jsonl.*

### 10e. Transport selection guide missing
- [x] **Add 3-line decision tree in `SKILL.md §Transport`**
  - stdio if launched as subprocess (Claude Desktop, CLI hosts) → Streamable HTTP if shared between containers or accessed over network → with auth if exposed outside trusted network
  - *closed 2026-05-22: 3-line decision tree added at the top of the Transport section.*

---

## Verification after closure

- [x] All checkboxes ticked above
- [ ] `meta/.claude-plugin/plugin.json` version bumped
- [ ] `./scripts/build-marketplace.py --sync` run
- [ ] `git status` reviewed; commit

---

## History
- 2026-05-22 — file created from review synthesis
- 2026-05-22 — all 23 action items closed via parallel subagent dispatch (Sonnet for prose/judgment, Haiku for mechanical); orchestrator dochistka pass for snake_case stragglers and stale security.md cross-refs.
