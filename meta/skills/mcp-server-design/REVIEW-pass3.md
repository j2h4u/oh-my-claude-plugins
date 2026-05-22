# REVIEW pass 3 — three-reviewer audit

Combined findings from three parallel reviewers (newcomer, pragmatic skeptic, coherence auditor)
against the `mcp-server-design` skill corpus.

Reviewers had different optics:
- **Newcomer**: first contact, end-to-end reading, looks for WTF moments and actionability cliffs
- **Skeptic**: challenges every non-trivial claim; finds over-engineering, cargo-cult, unsupported assertions
- **Coherence**: reads everything, finds contradictions, dead links, scope-tag mismatches between files

---

## Auto-applied (no decision needed)

These were applied immediately during this pass — pure factual fixes with no judgment involved.

- [x] `SKILL.md:46` — Security review section numbers were `1, 4, 8`, but §14 is Security, §12 Transport, §5 Parameter Schemas → fixed
- [x] `SKILL.md:73,210` — `"15-section"` checklist count, actual is 16 → fixed
- [x] `audit-checklist.md:117` — budget reference pointed to `tool-design.md` which has no such section; canonical text lives in `SKILL.md §Agent UX` → repointed
- [x] `design-philosophy.md:44` — `"single digits"` (≤9) conflicted with `≤10` used in 4 other files → unified to `≤10`
- [x] `SKILL.md:130`, `audit-checklist.md:114`, `agent-ux.md:139`, `tool-design.md:121` — `SubmitFeedback` (PascalCase) used as tool-name reference; canonical name is `submit_feedback` (snake_case) per the recent commit normalizing naming → fixed in code references; left in description trigger text (`SKILL.md:6`) since that's a user-facing search phrase
- [x] `audit-checklist.md:124` — stderr rule did not surface the daemon exception (only the `[CONDITIONAL]` tag, no pointer) → added inline pointer to `daemon-architecture.md` per `SKILL.md:168`

---

## Decisions needed — walk-through list

Items grouped by category. Each item has context and the choice to make.
Tick `[x]` after we decide and apply.

### A. PascalCase vs snake_case in narrative examples ✅ DONE

**Decision:** sweep all to snake_case (snake_case is the rule; examples must follow it).
Verified clean across `SKILL.md` and all `references/*.md`.

- [x] `audit-checklist.md:20` — `track_latest_order`, not `get_order_status`
- [x] `audit-checklist.md:79` — `use list_dialogs to get valid IDs`
- [x] `agent-ux.md:74-77` — workflow block now uses `search_messages`, `list_messages`, `list_dialogs`
- [x] `agent-ux.md:114, 116` — error-example block now uses `list_dialogs`, `get_entity_info`
- [x] `SKILL.md:6` — trigger phrase `add submit_feedback tool`
- [x] `SKILL.md:106` — title contrast: `"Search messages"` vs raw tool name `search_messages`
- [x] `design-philosophy.md:122` — already snake_case (false alarm in earlier review)

### B. `[posture]` prefix — untested concept tested by audit ✅ DONE

**Research findings** (Anthropic engineering docs, MCP spec, Faghih et al. EMNLP 2025,
BiasBusters, GitHub MCP): no empirical evidence for `[primary]/[secondary]` prefix; the
validated levers are assertive description language, namespacing in names, formal MCP
annotations, and sharper descriptions.

- [x] Cut `[posture]` section from `agent-ux.md` (was lines 36-46)
- [x] Replaced with **"What Actually Moves Tool Selection (empirically validated)"** section
  listing the proven levers with research citations (Anthropic blog, arxiv:2505.18135, MCP spec)
- [x] Removed `audit-checklist.md:52` `[posture]` audit item; replaced with an item that
  audits **assertive proactive language** in descriptions (which IS validated) pointing to the
  new agent-ux.md section

### C. Cut self-flagged optional content

Authors mark these sections as "skip unless you need it" — skeptic asks why they're in a
production-grade skill.

- [ ] `feedback-tool.md §Session-Level Task Tracking` (`declare_session_task`). Cost
  "non-trivial" per the authors. Cut to one-paragraph mention with link out, or remove entirely.
- [ ] `agent-ux.md §Post-MVP Tool Surface Normalization` (~280 words). Generic design-review
  template, not MCP-specific. Skeptic recommends collapse to one bullet in `audit-checklist.md`.

### D. Generic content masquerading as MCP-specific

Skeptic flagged several sections that are largely generic SWE/SRE/security advice with thin
MCP wrapping.

- [ ] `security-threats.md §3` (Authentication and authorization) — generic OWASP material
  (IDOR, SQL injection, path traversal, command injection). MCP-specific angle is **one**
  bullet: args come from LLM, not from a user. Decide: trim aggressively, or keep as
  "compliance checklist for completeness".
- [ ] `security-threats.md §7` (Supply chain) — 80% generic devsecops (pinning, 2FA,
  lockfiles). MCP-specific is one bullet (semver for tool surface).
- [ ] `observability.md` — generic SRE logging-101 (instrument at boundary, finally block,
  logging-must-not-fail). Decide: trim or keep as on-ramp for newcomers.
- [ ] `audit-checklist.md` — 80+ items across 16 sections. Skeptic estimates ~20 are
  MCP-specific, rest generic API/security hygiene. Decide: shrink to MCP-only, or mark
  generic items with a `[GENERIC]` tag so readers can skip if they already do general
  security review elsewhere.

### E. Empirical claims missing evidence

These sound authoritative but rest on single observations or anecdotes:

- [ ] `clients.md:67` "Socket closes after ~26 seconds" — `n=1`. Already honestly tagged in
  `clients.md`, but `SKILL.md` and `audit-checklist.md` cite the 20-second design target as if
  it were spec. Add `[EMPIRICAL, n=1]` qualifier wherever it appears outside `clients.md`.
- [ ] `tool-design.md:75` `"≤10 primary tools"` — backed by 2 anecdotes (GitHub MCP 40→3-10,
  Block Linear 30→2). Decide: keep `≤10` with a clearer caveat ("rule of thumb from a handful
  of high-profile collapses; ceiling depends on description quality and domain coherence"),
  or drop the precise number and say "single-purpose servers, prune aggressively".
- [ ] `agent-ux.md §ALL-CAPS named workflow patterns` — claim that "agents will literally
  invoke 'the SEARCH THEN READ workflow' in their reasoning." Sourced from one server. Decide:
  qualify as `[OPINIONATED, candidate]`, or remove.
- [ ] `agent-ux.md` — "LLM-optimal description is also informative to humans; the reverse is
  not guaranteed." Asserted as fact, no evidence. Decide: drop, or rephrase as conjecture.
- [ ] `observability.md` — "Tools called 0–2 times across thousands of sessions are not
  discoverable, not useful, or both." Decide: add the caveat that some tools are
  correctness-critical despite low frequency (don't delete blindly).
- [ ] Across all `OPINIONATED` items in the corpus: add an `Evidence:` one-liner (source / n /
  context). Skeptic's strongest recommendation. If you can't write the line, cut the item.

### F. New-reader onboarding gaps

Newcomer found no path from "first read" to "build first server".

- [ ] **Quick Start path** in `SKILL.md` — 5-7 numbered steps that take a reader from "I want to
  build an MCP server" to "I have a smoke-tested first tool". Currently the table jumps
  straight into 12 references / ~3000 lines.
- [ ] **Glossary** in `SKILL.md` — one-line definitions for `structuredContent`, `outputSchema`,
  `isError`, `server.instructions`, `stdio`, `Streamable HTTP`, `posture`, tool `annotations`.
  Definitions exist but are scattered across 11 files.
- [ ] **Hello-World example** — current examples are fragments from real servers (telegram /
  ozon). Add one self-contained 30-line working server (Python preferred for `[STACK:Python]`
  default) showing: `name`, `title`, `outputSchema`, `isError`, stderr logging.
- [ ] `gateway-aggregation.md` — add a one-line disclaimer in the **first** paragraph: "Skip
  entirely if you're only building a single MCP server; this file is about aggregating
  multiple servers behind a gateway." Currently the disclaimer is buried.

### G. Structural / coherence cleanups

- [ ] **Quick Checks duplication** — three lists overlap (`SKILL.md:217-230`,
  `observability.md:211-216`, `security-threats.md:373-383`). Decide: one master list in
  `SKILL.md`, others cross-link with file-scoped delta only; or scope each list narrowly to
  its file's domain.
- [ ] **Async-handle pattern wording** — `tool-design.md:288-303` says "return id + status:
  working, separate poll tool"; `clients.md:92-93` says "return partial result + agent
  polls via follow-up". These are different patterns. Pick one canonical phrasing, cross-link.
- [ ] **Missing rows in `SKILL.md` Use-Case table** — `long-running operations` and
  `declare_session_task` / session-task tracking have no entry. Add rows or accept they're
  intentionally hidden.
- [ ] **`clients.md` missing from "Designing"** row in the Use-Case table — currently only
  appears under "Security review" and indirectly via Transport. Newcomer would benefit from
  reading client limitations during design, not after.
- [ ] **Orphan concepts**: `io.modelcontextprotocol/ui` (clients.md:44, 113),
  `x-fastmcp-wrap-result` (fastmcp-notes.md:20), "BFF pattern" (design-philosophy.md:111),
  "cognitive congruence" (agent-ux.md:188). Either thread them through or remove.

### H. Decisions matrices over prose

Newcomer suggested decision-trees instead of tables in places where reading order matters:

- [ ] `SKILL.md:42` Use-case table → flowchart
- [ ] `SKILL.md:160` Transport choice (currently one-liner with arrows) → expand or formalise
- [ ] `observability.md` JSONL / SQLite / OTel three-pattern → decision-tree (start here →
  scale up to this)
- [ ] `python-notes.md` Fix 1 / Fix 2 / Fix 3 — "in order of preference" but Fix 2 is also
  labelled "quick workaround". Clarify which is the mainstream recipe.

---

## Reviewer net verdicts (raw)

- **Newcomer:** strong scope tags, strong security-threats §0, but no quick-start path, no
  glossary, no working example, and references contain untested hypotheses framed as advice.
- **Skeptic:** mixed — distillation of real experience (anyOf-null fix matrix, Claude Desktop
  empirical findings, FastMCP issue numbers) plus a layer of generic SWE camouflage. Strongest
  fix: `Evidence:` line per `OPINIONATED` item.
- **Coherence:** scope-tag system works in principle but applied unevenly; section-number
  cross-refs broken in two places; PascalCase examples directly contradict the just-landed
  snake_case convention.

---

*End of pass-3 review. Next pass should walk this list top-to-bottom.*
