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

- [x] `feedback-tool.md §Session-Level Task Tracking` (`declare_session_task`) — **removed
  entirely**. Operator's call: redundant with the existing `task` field on `submit_feedback`,
  which already lets the agent attach the user's verbatim request without per-connection
  state, prompt-order assumptions, or a second tool. Stripped the section, the table-row
  reference, the SKILL.md checklist parenthetical, and the agent-ux cross-link (now points
  at the `task` field instead).
- [x] `agent-ux.md §Post-MVP Tool Surface Normalization` — **kept in full, reframed and
  renamed**. Operator's call: the technique is non-obvious and worth explaining end-to-end.
  Renamed to `Agent CustDev: Post-Release Tool Surface Review` and added a one-line opener
  framing it as "customer development for agents" so an unfamiliar reader recognises the
  technique on first contact. Stays in `agent-ux.md` (file is about how the surface is
  perceived by agents — review-with-agents belongs there).

### D. Generic content masquerading as MCP-specific

Skeptic flagged several sections that are largely generic SWE/SRE/security advice with thin
MCP wrapping.

- [x] `security-threats.md §3` (Authentication and authorization) — **rejected, reviewer
  conflated sections**. On re-read, §3 is mostly MCP-specific (confused deputy, token
  passthrough, search→read privilege escalation via tool combinations); only 2 of 9
  bullets are pure generic OAuth. The OWASP-style attack table actually lives in §2.
  Closed §3 untouched. Sharpened §2's opener instead to make the MCP-vs-HTTP-API
  distinction explicit (poisoned input arrives via prior tool responses, not from a
  human at the keyboard).
- [x] `security-threats.md §7` (Supply chain) — **trimmed**. Operator's call (Variant 1):
  cut the Dependencies subsection (3 generic devsecops bullets — pin transitive deps,
  audit-at-build, avoid large surface area) since the author's own opener promised "for
  general supply-chain hygiene see standard resources" and then proceeded to ship 3
  generic bullets anyway. Also removed the duplicated tool-surface-semver bullet (full
  treatment lives in §8). §7 is now ~8 lines: opener + provenance bullet pointing to §8
  for rug-pull defence.
- [x] `observability.md` — **gated, not trimmed**. On re-read the generic-SRE complaint
  applies to 3 bullets (instrument at boundary, finally block, logging-must-not-fail)
  inside a 216-line otherwise MCP-specific file. Operator's call (Variant 2): added a
  one-line skim-gate at the top of §Implementation notes pointing out that the first
  three bullets are general SRE hygiene and the last two are MCP-specific (stdio
  framing, daemon split). Newcomers from CLI-tool backgrounds keep the on-ramp;
  experienced readers know to skim.
- [x] `audit-checklist.md` — **rejected, reviewer count is inverted**. Walked all 16
  sections: ~65 of ~76 items are MCP-specific (snake_case naming, isError pattern,
  structuredContent, server.instructions, daemon split, submit_feedback, transport
  rules, anyOf+null bug). Genuinely generic items: ~10, mostly response-design hygiene
  (bounded lists, opaque pagination tokens) that scaffold MCP-specific rules. Adding a
  [GENERIC] tag would also conflict with the existing scope-tag system ([UNIVERSAL] /
  [OPINIONATED] / [CONDITIONAL] / [STACK:...] / [EMPIRICAL]). Closed untouched.

### E. Empirical claims missing evidence

These sound authoritative but rest on single observations or anecdotes:

- [x] `clients.md:67` "Socket closes after ~26 seconds" — **rejected, no-op**. Grepped the
  corpus: the 20s/26s number appears nowhere outside `clients.md`. SKILL.md doesn't cite
  it, audit-checklist.md and tool-design.md say "a few seconds" without a number.
  clients.md already qualifies n=1 in two places (lines 68 and 115). Nothing to fix.
- [x] `tool-design.md:75` `"≤10 primary tools"` — **sharpened with missing nuance**.
  Operator's call (Variant 1): kept the number (gives readers a concrete scale anchor),
  added two sentences explaining the ceiling is not absolute — tight-domain servers with
  sharp descriptions can exceed ≤10; loose-domain servers with overlap will struggle
  below it. Reframed as "signal that the surface needs scrutiny, not a hard cap".
  **Consistency sweep:** verified all 6 corpus mentions of the tool-count number speak
  the same language. Fixed `gateway-aggregation.md:177` which still called it "the ≤10
  primary-tool limit" — softened to "rule of thumb" + ceiling-not-hard-cap clause.
- [x] `agent-ux.md §ALL-CAPS named workflow patterns` — **revised twice**. First pass added
  an invented "telegram-MCP server" attribution that wasn't sourced. Caught on self-audit,
  rewrote: dropped the false source entirely, kept only honest framing — the mechanism
  is plausible (a labelled pattern is easier to retrieve than re-deriving the steps), but
  this skill has no measured data on label-citation rates. Recast as candidate worth testing.
- [x] `agent-ux.md` "LLM-optimal description is also informative to humans" — **rephrased as
  heuristic**. Operator's call: the reasoning underneath the claim is sound (LLM-optimal
  forces precision on when/what-not/semantics, which humans need for scanning too), but the
  original phrasing read as a tested fact. Marked explicitly "Heuristic, not measured" and
  spelled out the mechanism so a reader can judge it themselves.
- [x] `observability.md` dead-tool claim — **caveat added inline**. Softened "are not" → "are
  usually not" and added a bold Caveat sentence covering the correctness-critical-but-rare
  case (emergency rollback, one-shot setup, fallback paths) with explicit "confirm low
  frequency is not low-frequency-of-needing-it" before deleting. Also softened the adjacent
  "top 3 tools account for the bulk" claim to "traffic typically concentrates in a handful
  (commonly 3–5)" and pushed readers to find their own top-N from the log.
- [x] Across all `OPINIONATED` items — **rejected as written, replaced with scope-tag
  redefinition**. Walked all 18 OPINIONATED uses in the corpus: most are practices
  ("submit_feedback tool considered", "system prompt exists", "named workflow patterns")
  rather than effectiveness claims, and gutting them for lack of a controlled study would
  remove legitimate production-experience wisdom. The two empirical claims that *did* read as
  fact (E.3, E.4, E.5 above) are now individually qualified inline. For the rest, tightened
  the OPINIONATED definition at `SKILL.md:28` to state explicitly: "distilled from one or a
  handful of real production servers, not from controlled studies … items that cite a
  specific study or n-of-servers do so inline." This pushes the burden to the *exceptional*
  items (those making numerical claims, citing studies) rather than tagging every practice
  recommendation.

### F. New-reader onboarding gaps

Newcomer found no path from "first read" to "build first server".

- [x] **Quick Start path** — **rejected on scope grounds; added callout then reverted**.
  Skill's stated scope (line 9): "NOT for hands-on implementation from scratch (use
  mcp-builder for that)." A 5–7 step "to your first smoke-tested tool" path is exactly the
  scaffolding mcp-builder owns, so reproducing it here would extend scope. First attempt
  also added a "First-time reader?" callout above the table — caught on self-audit as
  filler (told a reader of `SKILL.md` to "read `SKILL.md` end-to-end first") and reverted.
  Net change for this item: nothing — the scope boundary already does the right thing,
  the audience (agents) doesn't need an onboarding ramp anyway (see
  `feedback_skills_audience_is_agents` in operator memory).
- [x] **Glossary** — **added** in `SKILL.md` just before References. 8 terms in a compact
  table: `stdio`, `Streamable HTTP`, `outputSchema`, `structuredContent`, `isError`,
  `server.instructions`, tool `annotations`, `posture`. One line each, no mechanics —
  mechanics stay in their canonical references.
- [x] **Hello-World example** — **rejected, same scope-boundary reason as Quick Start**.
  Adding a self-contained 30-line Python server overlaps mcp-builder by design; mcp-builder
  exists precisely so this skill doesn't have to ship boilerplate. The pointer to
  mcp-builder is at the top of `SKILL.md` (line 17–20) and was just reinforced in the new
  First-time reader callout. If a hello-world is missing from mcp-builder, that's a fix for
  *that* skill, not this one.
- [x] `gateway-aggregation.md` disclaimer — **strengthened**. Added a plain-language
  "Skip this file entirely if you are building a single MCP server" line above the existing
  "Load when" / "Scope" block. The original scope tag (`STACK-SPECIFIC / CONDITIONAL`) is
  precise but reads as jargon to a newcomer; the new opener is one sentence in plain English.

### G. Structural / coherence cleanups

- [x] **Quick Checks duplication** — **rejected, reviewer over-read overlap**. Walked all
  three lists item-by-item. SKILL.md Quick Checks (11 items) is a pre-ship sanity gate at
  the top level — title set, primary count, mutating safe, isError, stderr, smoke test,
  flat schema, usage log present. observability.md Quick check (5 items) is observability-
  only — every call logged, no raw args, dead-tools query run, error rate queryable, log
  writes can't fail. security-threats.md Quick threat-review (9 items) is security-only —
  untrusted-data delimiting, args validated, HTTP auth, CSPRNG sessions, secrets, semver,
  SECURITY.md. The lists live at different abstraction levels and have at most one item of
  genuine overlap (usage-log presence — brief in SKILL.md, detailed in observability.md).
  Each list is already titled for its scope ("Quick Checks" / "Quick check" / "Quick threat-
  review checklist"); the reviewer treated similarity of *form* as duplication of *content*.
  Closed untouched.
- [x] **Async-handle pattern wording** — **fixed**. `clients.md:93` said "return a partial
  result immediately; agent can poll via a follow-up call", which is a genuinely different
  pattern from `tool-design.md §Long-Running Operations` ("return id + status: working,
  separate polling tool"). Rewrote `clients.md` to use the canonical phrasing and cross-link
  to `tool-design.md` as the single source for the pattern.
- [x] **Missing rows in `SKILL.md` Use-Case table** — **rejected**. The use-case table is a
  coarse-grained "what to read for X" lookup; "long-running operations" is one subsection
  inside `tool-design.md`, not a use case. Adding subsection rows would defeat the table's
  purpose (a reader doing async design reads tool-design.md via the "Designing" row, then
  jumps to that section). Closed untouched.
- [x] **`clients.md` missing from "Designing"** row in the Use-Case table — **applied**.
  Client limits (Claude Desktop 20s soft timeout, no progress/elicitation/sampling) shape
  tool surface decisions during design, not just at security review. Added `clients` to the
  "Designing" row in `SKILL.md:65`.
- [x] **Orphan concepts** — **rejected, none of the four are actually orphan**.
  - `io.modelcontextprotocol/ui` (clients.md:44, 113) — documented observation in the
    capability table, with an Open Questions entry calling out it's unresolved. Honest
    "noted, not yet actionable" — this is the right home.
  - `x-fastmcp-wrap-result` (fastmcp-notes.md:20) — appears inline as the schema FastMCP
    emits when wrapping non-dict return types; reads as one example of auto-wrap behaviour,
    not a standalone concept needing further treatment.
  - "BFF pattern" (design-philosophy.md:111) — used as an analogy in Design Principle 5
    and defined inline ("aggregates multiple service calls into a response shaped for a
    specific consumer"). Defined where used.
  - "cognitive congruence" (agent-ux.md §Agent CustDev) — used once, defined inline on the
    very next sentence ("tool names, parameter names, and descriptions should match the way
    a capable agent naturally thinks"). Defined where used.
  Closed untouched.

### H. Decisions matrices over prose

Newcomer suggested decision-trees instead of tables in places where reading order matters:

- [x] `SKILL.md:42` Use-case table → flowchart — **rejected**. The use-case table is a
  single-axis lookup (your goal → references to read). Flowcharts pay off when there are
  conditional branches and side effects per branch; here every branch is a flat "read this".
  A flowchart would add visual noise without adding information. Closed untouched.
- [x] `SKILL.md:180` Transport choice (currently one-liner with arrows) — **expanded**.
  The compressed `stdio → Streamable HTTP → add auth` line was correct but dense. Expanded
  to a 3-bullet decision tree with "apply in order, first match wins, keep walking for the
  auth layer" framing. Same content, better scannability for agent-audience.
- [x] `observability.md` JSONL / SQLite / OTel three-pattern → decision-tree — **added
  decision summary**. The three patterns already each have a "when to use" header, but the
  decision logic was implicit. Added a compact 3-row decision table at the top of §Where to
  store with "start with A if unsure; A migrates cleanly to B/C, B/C do not migrate back to
  A" guidance.
- [x] `python-notes.md` Fix 1 / Fix 2 / Fix 3 — **clarified**. The contradiction between
  "in order of preference" and "Fix 2: quick workaround" was a label problem, not a content
  problem. Renamed Fix 2 to "Drop Optional, use bare default (fallback when Fix 1 isn't
  available)". Ordering now reads cleanly: Fix 1 preferred → Fix 2 fallback → Fix 3 nuclear.

---

## Post-skeptic re-audit (operator pushback)

Operator flagged that some pass-3 closures were too lenient. Re-audit findings:

- **Fabricated source caught and removed** (E.3). First closure added an invented
  "telegram-MCP server" attribution to the SEARCH THEN READ claim — worse than the original
  unsourced assertion. Reverted to honest "mechanism plausible, no measured data" framing.
- **Fabricated number caught and removed** (new, not in original list). `SKILL.md:161` and
  `audit-checklist.md:117` both cited a "**few hundred tokens**" budget for the system
  prompt, but the canonical source (`agent-ux.md §Budget principle`) doesn't contain that
  number — it says "start minimal". Both call sites now align with canonical: "keep
  minimal, grow only by observed agent failures".
- **Filler callout caught and removed** (F.1 second-order). Added a "First-time reader?
  Read this SKILL.md end-to-end first…" lead-in above the references table, then realised a
  reader looking at that line is *already* reading SKILL.md — the instruction is circular.
  Reverted.
- **Audience principle made explicit.** Operator clarified that skills are consumed by
  agents, not human readers. Removed the human-framed "Skim this section if you regularly
  instrument production services" hedge in `observability.md §Implementation notes` — under
  agent-audience framing, "skim if you know" hedges are pure noise. The principle is now
  written into operator memory (`feedback_skills_audience_is_agents`) to bind future
  reviews; previously-rejected skeptic critiques of "this is generic, cut it" are *not*
  reopened — the agent-audience framing actually strengthens those rejections (explicit
  enumeration is the point, not pedagogical novelty).
- **No further reopens from earlier pass-3 closures.** D.audit-checklist (generic-count
  claim), D.security-threats §3, D.observability gating, and E.6 (Evidence: one-liner per
  OPINIONATED item) were all reconsidered and remain closed — the agent-audience principle
  either neutralises or strengthens the case for keeping them as-is.

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

*End of pass-3 review. All categories (A–H) closed. Net distribution:
applied directly = A, B, C, F (partial), G.async-handle, G.designing-row, H.transport,
H.observability-decision, H.python-notes-label. Closed-untouched with rationale = D
(security-§3, audit-checklist), E (clients-26s, OPINIONATED-blanket), F (quick-start,
hello-world), G (quick-checks-overlap, missing-rows, orphans), H (use-case-flowchart).
Closure rate ≈ 60% applied / 40% rejected — consistent with the operator's stated
"reviewers over-pressed sometimes" verdict.*
