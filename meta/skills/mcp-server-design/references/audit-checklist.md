# MCP Server Audit Checklist

> Load when auditing an MCP server. Mark each item `✅` / `❌` / `— N/A`; collect `❌` into findings with fixes. `*` = high-priority. Scope tags: `[UNIVERSAL]` / `[OPINIONATED]` / `[CONDITIONAL]` / `[STACK:...]` / `[EMPIRICAL]` (recheck on version bumps) — defined in `SKILL.md §Scope Tags`.

---

## 1. Design Philosophy

- [ ] * `[OPINIONATED]` **Tool count under scrutiny** — count primary tools in the registry. >10 is a signal to consolidate or split into domain servers, not a hard cap. See [tool-design.md §Tool Classification](tool-design.md#tool-classification--primary-vs-secondary-and-the-10-tool-signal) for rationale and exceptions.
- [ ] * `[UNIVERSAL]` **No thin API wrapper** — for each tool, ask: "does this map 1:1 to a backend endpoint?" If yes, it should bundle the downstream calls internally instead.
- [ ] * `[UNIVERSAL]` **Outcome orientation** — each tool name describes a user goal, not an operation. `track_latest_order`, not `get_order_status`.
- [ ] `[UNIVERSAL]` **One server, one job** — can you describe the server's purpose in one sentence? If not, scope is too broad.
- [ ] * `[OPINIONATED]` **80/20 check** — **N/A for new servers.** This audit requires ≥30 days of production tool-call logs. Recheck at 30 days; until then, focus on items §2 onward. Once logs exist: are there tools nobody calls? Run a dead-tool query against the usage log (30+ days, hundreds of calls minimum). Tools with ~0 calls: rewrite description first, delete next review cycle if still dead. See [observability.md](observability.md). If no usage log exists, that is itself a finding — fix observability first, then audit.

---

## 2. Tool Naming and Classification

- [ ] `[UNIVERSAL]` **`snake_case` verb_noun names** — `list_dialogs`, `get_entity_info`. No `getData`, `RunQuery`, `handle_request`. Pattern: `^[a-z0-9_]{1,64}$`. → [tool-design.md §Naming](tool-design.md)
- [ ] * `[OPINIONATED]` **`title` field set on every tool** — 1–3 words, sentence case, product language. Not a reformatted `name` ("Search Ozon", not `"Search Ozon"` = `ozon_search`). *Skip when:* no client in your target matrix surfaces `title` distinctly from `name`.
- [ ] `[OPINIONATED]` **Primary/secondary classification consistent** — primary tools are user-facing capabilities; secondary/helper tools are plumbing. No primary tool that's implementation detail. *Skip when:* surface has <5 tools (no posture distinction is load-bearing).
- [ ] `[EMPIRICAL]` **No namespace collision risk** — tool names don't collide with well-known client meta-operations (e.g. `get_me` → `get_my_account`).

---

## 3. Tool Annotations

- [ ] `[UNIVERSAL]` **`readOnlyHint` set on read-only tools** — tools that make no state changes declare `readOnlyHint: true`. Default is `false`; missing annotation is a miss.
- [ ] `[UNIVERSAL]` **`destructiveHint` set to `false` on additive writes** — e.g. `submit_feedback` is additive, not destructive.
- [ ] `[UNIVERSAL]` **`idempotentHint` set where applicable** — tools safe to retry (same args → same result) declare it.
- [ ] `[UNIVERSAL]` **`openWorldHint: false` on local-only tools** — tools that don't touch external services should not carry the default `true`.
- [ ] * `[UNIVERSAL]` **Mutating tools are safe by default** — costly or destructive tools create drafts/paused resources, use dry-run/preview, or require explicit activation.

---

## 4. Tool Descriptions

- [ ] * `[UNIVERSAL]` **LLM-oriented** — descriptions answer: "When should I call this?", "What does it do?", "What should I NOT do with it?" Not just a one-line summary.
- [ ] `[UNIVERSAL]` **Proactive triggers** — descriptions say "Use proactively when…" for tools that agents should call without being asked.
- [ ] `[UNIVERSAL]` **Parameter semantics in prose** — field meanings explained in description, not just in schema. The LLM reads descriptions; schema is for validation.
- [ ] `[UNIVERSAL]` **Response shape documented** — non-trivial tools describe key fields, units, truncation, and whether text is a preview of `structuredContent`.
- [ ] `[CONDITIONAL]` **Static reference material uses Resources** — field catalogs, enum lists, query syntax, and service limits are exposed as MCP Resources instead of repeated in tool descriptions.
- [ ] `[OPINIONATED]` **Assertive proactive language present where relevant** — for tools the agent should call without being asked, the description includes a direct directive ("Use this proactively whenever…"). This is the empirically validated lever for biasing tool selection — see `agent-ux.md §What Actually Moves Tool Selection`. *Skip when:* every tool is reactive-only (only invoked on direct user request).

---

## 5. Parameter Schemas

- [ ] * `[UNIVERSAL]` **No untyped nested objects** — no bare `filters: dict`, no `options: object` without `properties`. Typed nested models with fully-declared `properties` are acceptable at ≤1 level; ≥2 levels hallucinate regardless of typing. → `tool-design.md §Argument Flattening`
- [ ] `[UNIVERSAL]` **Enums over free strings** — closed value sets use `Literal` / `enum`, not free `str`.
- [ ] `[UNIVERSAL]` **Optional parameters have sensible defaults** — optional means meaningful behaviour without the argument, not "nullable required".
- [ ] `[UNIVERSAL]` **Non-obvious parameters self-document** — IDs, dates, limits, and ambiguous strings carry a description/pattern/example in the schema, not just a type. Use whatever idiom your SDK exposes for this.
- [ ] `[EMPIRICAL]` **`anyOf:[T, null]` stripped** `[Claude Desktop]` — fix + SDK auto-strip status: `tool-design.md §Schema Compatibility Gotcha`
- [ ] `[UNIVERSAL]` **`min_length=1` is not enough** — whitespace-only strings checked explicitly; `"   "` passes `min_length=1`.

---

## 6. Structured Output

- [ ] `[UNIVERSAL]` **`outputSchema` declared on structured tools** — tools returning lists, status objects, or metadata have `outputSchema` defined.
- [ ] * `[UNIVERSAL]` **`structuredContent` returned on every successful call** — if `outputSchema` is declared, `structuredContent` MUST be present every time, not conditionally.
- [ ] `[UNIVERSAL]` **Text `content` present alongside `structuredContent`** — backwards-compat for older clients. Text is a human-readable summary of the same data, not a repeat of the raw JSON.

---

## 7. Error Handling

- [ ] * `[UNIVERSAL]` **Business errors use `isError: true`** — validation failures, API failures, entity-not-found — all returned as tool results with `isError: true`, not raised as exceptions.
- [ ] `[UNIVERSAL]` **Protocol errors reserved for protocol failures** — JSON-RPC exceptions only for malformed requests, unknown tool names. Not for domain errors.
- [ ] `[UNIVERSAL]` **Error messages are actionable** — every recoverable error includes an `Action:` hint or names a tool the agent can call next. "Entity not found — use `list_dialogs` to get valid IDs."
- [ ] `[UNIVERSAL]` **Generic backend errors preserve diagnostics** — "Bad Request", "Internal Server Error", or "not found" include safe field-level details, response excerpts, or correlation IDs; secrets are redacted.
- [ ] `[CONDITIONAL]` **Backend-unavailable errors explicit** — if the daemon/backend is down, the error message says so clearly ("daemon not running — start with: …"), not a raw socket exception.

---

## 8. Response Design

- [ ] `[UNIVERSAL]` **All list responses are bounded** — no tool returns unlimited results. Hard cap enforced. Message shown when results are truncated ("N more — use cursor X to continue").
- [ ] `[UNIVERSAL]` **Pagination tokens are opaque** — tokens encode enough state to reproduce the next page; agents don't need to parse them.
- [ ] `[UNIVERSAL]` **Pagination token validated on next call** — mismatch (wrong dialog, wrong context) returns explicit error, not silent wrong results.
- [ ] `[UNIVERSAL]` **Empty results distinguished from errors** — "no results" and "search failed" are different responses.
- [ ] `[OPINIONATED]` **Tabular text output is compact** — text `content` does not repeat large JSON; use compact tables/CSV previews while preserving required `structuredContent`. *Skip when:* server has no tabular tools (only free-form summaries, confirmations, or single-object responses).

---

## 9. Long-Running Operations

- [ ] `[UNIVERSAL]` **No blocking tools > a few seconds** — tools that invoke slow external APIs, file processing, or background sync use the async handle pattern (return task ID immediately, separate polling tool).
- [ ] `[UNIVERSAL]` **Handle pattern implemented correctly** — the first tool never blocks; it only enqueues and returns a handle.

---

## 10. Agent Feedback Channel

- [ ] `[OPINIONATED]` **`submit_feedback` tool considered** — useful pattern for servers where a maintainer actively reviews the feedback queue; mark N/A if no queue is monitored. Write-only, fire-and-forget, no read-back tool.
- [ ] `[CONDITIONAL]` **`submit_feedback` description includes proactive triggers** — if the tool exists: verbatim triggers when a tool returned unexpected output, error is unclear, capability was missing, behaviour contradicts docs.
- [ ] `[CONDITIONAL]` **Operator CLI exists** — if the tool exists: `feedback list`, `feedback status <id> <status>`, `feedback delete <id>`.
- [ ] `[CONDITIONAL]` **Separate storage** — if the tool exists: feedback persists in its own DB/file, not mixed with server's main data.

---

## 11. System Prompt (`server.instructions`)

- [ ] `[OPINIONATED]` **System prompt exists and is non-empty** — server has `server.instructions` set. *Skip when:* no domain-specific orientation is load-bearing (tool descriptions already carry every directive). Empty/near-empty `server.instructions` is worse than absent — omit entirely if there is nothing to say.
- [ ] `[OPINIONATED]` **Feedback directive present** — verbatim string: "Use `submit_feedback` immediately when a tool response is wrong, surprising, or missing a useful capability — don't wait until end of session." Canonical owner: `agent-ux.md §System Prompt as Configuration Surface`. *Skip when:* §10 `submit_feedback` is N/A (no maintainer queue) — a directive referencing a non-existent tool is worse than no directive.
- [ ] `[OPINIONATED]` **Named workflow patterns (ALL-CAPS)** — at least one named pattern for the most common multi-step flow. *Skip when:* server's surface has no multi-step flow worth naming (every tool stands alone).
- [ ] `[OPINIONATED]` **Live state injected at startup** — connected account, active limits, or other runtime state built dynamically, not hardcoded at deploy time. *Skip when:* server is stateless / per-session state is captured fully in tool responses.
- [ ] `[OPINIONATED]` **System prompt is minimal, not maximal** (see `SKILL.md §Agent UX` and `agent-ux.md §System Prompt as Configuration Surface`) — every directive justified by an observed agent failure without it. Growth is a smell: either the missing piece is a tool, or the directive belongs in a tool description.

---

## 12. Transport and Logging

- [ ] * `[UNIVERSAL]` **No HTTP+SSE transport (2024-11-05)** — deprecated. Only `stdio` or Streamable HTTP.
- [ ] * `[UNIVERSAL]` **All logging goes to `stderr`** — no `print()` or logger writing to `stdout`. Any `stdout` output corrupts the stdio transport silently. N/A only for Streamable HTTP servers (no stdio). **Exception:** under the daemon + on-demand pattern (see [daemon-architecture.md](daemon-architecture.md)), the MCP server must NOT write to `stderr` either — the daemon owns logging via socket.
- [ ] `[UNIVERSAL]` **Transport matches deployment** — `stdio` for subprocess clients (Claude Desktop), Streamable HTTP for inter-container or HTTP-capable clients.

---

## 13. Architecture (Daemon/Stateless split — if applicable)

> **Skip if:** single-process server without a persistent background resource (DB, WebSocket, ML model, Unix socket). All items below are N/A for stateless servers.

- [ ] `[CONDITIONAL]` **Stale socket file cleaned at daemon startup** — daemon deletes existing socket file before `bind()`, otherwise crashes with "address already in use" after unclean shutdown.
- [ ] `[CONDITIONAL]` **MCP server reads stdin until client closes** — not exiting after first response. Premature exit silently breaks stdio sessions.
- [ ] `[CONDITIONAL]` **Daemon-not-running error is user-facing** — `FileNotFoundError` / `ConnectionRefusedError` translated to a single actionable message, not leaked as a socket exception.
- [ ] `[CONDITIONAL]` **Crash isolation** — MCP server crash doesn't kill the daemon; daemon crash returns clean error on every tool call rather than crashing the MCP server.

---

## 14. Security

> Sub-grouped by concern so the auditor can triage one category at a time.
> `*`-marked items carry an inline *smell pattern* — the shape of a failing
> implementation. Use it to pass/fail from the checklist alone; dive into
> `security-threats.md` only when the smell matches.

### 14a. Inputs and data handling

- [ ] `[UNIVERSAL]` **Untrusted content delimited in responses** — message bodies, file contents, DB rows wrapped in explicit framing, not injected raw into tool output.
- [ ] `[UNIVERSAL]` **Tools that fetch external content flagged in descriptions** — agents know to treat results as data, not instructions.
- [ ] * `[UNIVERSAL]` **Inputs validated at system boundary** — paths, shell arguments, URLs, tenant IDs, and command flags are allowlisted/normalised before use. *Smell: raw tool args flowing into `open()`, `subprocess`, or HTTP fetches with no allowlist.*
- [ ] `[UNIVERSAL]` **Secrets never leak** — tokens, cookies, API keys, OAuth codes absent from URLs, logs, tool responses, and feedback records.

### 14b. Network exposure and transport

- [ ] `[UNIVERSAL]` **Local server not exposed on public interface** — binds to `127.0.0.1` or Unix socket, or has authentication if network-accessible.
- [ ] `[CONDITIONAL]` **Origin header validation for Streamable HTTP** — server rejects requests with invalid `Origin` (HTTP 403). Usually handled by SDK — verify it's not disabled.
- [ ] * `[CONDITIONAL]` **Streamable HTTP session IDs are CSPRNG** — ≥ 128 bits entropy, not derived from time/counter/PID. *Smell: session ID from `time.time()`, PID, counter, or `random.random()` instead of `secrets.token_urlsafe`.* → [security-threats.md §4 Session and transport security](security-threats.md)
- [ ] `[CONDITIONAL]` **`Host` header validated against allowlist** — defends localhost-bound HTTP servers against DNS rebinding. → [security-threats.md §4 Session and transport security](security-threats.md)

### 14c. Authorization

- [ ] * `[CONDITIONAL]` **OAuth: per-principal tokens, narrow scopes, no pass-through** — applies to servers acting as OAuth client or authorization server. *Smell: one shared upstream token for all users, no per-principal audit trail.* → [security-threats.md §3 Authentication and authorization](security-threats.md)
- [ ] * `[UNIVERSAL]` **Authorization checked per call, not only at search** — every read/write tool joins against the authenticated principal; no IDOR via `*_id` arguments. *Smell: `search_*` filters by principal, but `get_*`/`update_*` returns/writes by ID alone.* → [security-threats.md §3 Authentication and authorization](security-threats.md)

### 14d. Resource limits (DoS)

- [ ] `[UNIVERSAL]` **Per-tool timeout + concurrency cap + request/response size cap** — bounded resources prevent DoS by a buggy or hostile caller. → [security-threats.md §5 Resource exhaustion and DoS](security-threats.md)

### 14e. Release stability and supply chain

- [ ] `[UNIVERSAL]` **Tool surface changes go through semver + changelog** — no silent renames, no annotation flips, no description-only behaviour changes. → [security-threats.md §8 Release hygiene and surface stability](security-threats.md)
- [ ] `[UNIVERSAL]` **Lockfile committed; dependency audit (`npm audit`, `pip-audit`) gates CI.** → [security-threats.md §7 Supply chain — defending your own package](security-threats.md)

→ Deep threat reference for security review: [security-threats.md](security-threats.md)

---

## 15. Testing

- [ ] `[UNIVERSAL]` **Integration smoke test exists** — calls every tool through the actual transport against a live server. Unit tests alone don't cover transport or schema serialisation.
- [ ] `[OPINIONATED]` **Dark-room UX test done at least once** — agent given the server with no briefing, asked to complete a real task, feedback queue reviewed. If not done: mark as debt. → Protocol: `agent-ux.md §Dark-Room Test`. *Requires:* `submit_feedback` deployed and the feedback directive in the system prompt — gate on §10 first.
- [ ] `[OPINIONATED]` **Agent CustDev done at least once** — interview an agent that has used the server about pain points, missing primitives, confusing names. Distinct from dark-room: dark-room observes behaviour, CustDev solicits report. Both require `submit_feedback` deployed. → Protocol: `agent-ux.md §Two Kinds of Testing`

---

## 16. Observability

- [ ] * `[OPINIONATED]` **Per-call usage log exists** — every tool call recorded with at minimum `ts`, `tool_name`, `status`, `duration_ms`. Without it, §1 80/20 check cannot be answered. → [observability.md](observability.md). *Skip when:* pre-production / development server with no real traffic — mark as debt to fix before first production deploy.
- [ ] `[UNIVERSAL]` **No raw argument values or response bodies in the log** — only schema-only `args_shape`, sizes, and error classes. Raw values may carry secrets, PII, or prompt-injected content.
- [ ] `[OPINIONATED]` **Reports are runnable, not just data** — dead-tool, error-rate-per-tool, p95-latency-per-tool queries exist or are trivial to write (DuckDB / SQL / Loki). *Requires:* per-call usage log (previous item).
- [ ] `[OPINIONATED]` **Dead-tool query has been acted on at least once** — tool surface has been pruned or descriptions rewritten based on usage data. A log that is never read is theatre. *Requires:* ≥30 days of production log (§1 80/20 prerequisite).

---

## Findings Summary

After completing the checklist, compile:

```
HIGH (fix before shipping):
- [ item ] → [ what to fix ]

MEDIUM (fix this iteration):
- ...

LOW / DEBT (track, fix later):
- ...

N/A items:
- ...
```

Items marked `*` that failed → HIGH by default **only when their scope tag applies**.
