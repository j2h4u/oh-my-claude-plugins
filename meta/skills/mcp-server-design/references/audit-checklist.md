# MCP Server Audit Checklist

> **Load when:** Auditing an existing MCP server against skill guidelines.
>
> **How to use:** Go through each section. For each item mark `✅ pass`, `❌ fail`, or `— N/A`.
> Collect all `❌` items into a findings list at the end with the fix required.
> Items marked with `*` are high-priority — fix before anything else.
>
> **Scope tags:** `[UNIVERSAL]` applies to any MCP server. `[OPINIONATED]` is this skill's
> recommended production default, not a protocol requirement. `[CONDITIONAL]` applies only when
> the deployment shape matches. `[STACK:...]` applies only to that technology stack. `[EMPIRICAL]`
> is observed client behaviour and should be rechecked when versions change.

---

## 1. Design Philosophy

- [ ] * `[UNIVERSAL]` **Tool count controlled** — count all tools exposed in the registry. If > 15 primary tools, the surface likely needs consolidation or splitting into domain-specific servers.
- [ ] * `[UNIVERSAL]` **No thin API wrapper** — for each tool, ask: "does this map 1:1 to a backend endpoint?" If yes, it should bundle the downstream calls internally instead.
- [ ] * `[UNIVERSAL]` **Outcome orientation** — each tool name describes a user goal, not an operation. "TrackLatestOrder", not "GetOrderStatus".
- [ ] `[UNIVERSAL]` **One server, one job** — can you describe the server's purpose in one sentence? If not, scope is too broad.
- [ ] `[OPINIONATED]` **80/20 check** — are there tools nobody calls? Review call logs or feedback queue. Dead tools should be removed.

---

## 2. Tool Naming and Classification

- [ ] `[UNIVERSAL]` **`snake_case` verb_noun names** — e.g. `list_dialogs`, `get_entity_info`, `submit_feedback`. No `getData`, `RunQuery`, `handle_request` (too generic), no spaces or special chars. Characters: `^[a-zA-Z0-9_]{1,64}$` — what Claude's frontend validates.
- [ ] * `[UNIVERSAL]` **`title` field set on every tool** — 1–3 words, in the product's language, sentence case, user-facing. Claude Desktop shows this in "Claude is using…" blocks and the tool list. Without it the raw `name` is shown (`ozon_search`, `GetMyRecentActivity`) which leaks internal naming to users. Not a reformatted `name` — write what a user would say: "Search Ozon", "Recent activity", "Sync status".
- [ ] `[OPINIONATED]` **Primary/secondary classification consistent** — primary tools are user-facing capabilities; secondary/helper tools are plumbing. No primary tool that's implementation detail.
- [ ] `[EMPIRICAL]` **No namespace collision risk** — tool names don't collide with well-known client meta-operations (e.g. `GetMe` → `GetMyAccount`).

---

## 3. Tool Annotations

- [ ] `[UNIVERSAL]` **`readOnlyHint` set on read-only tools** — tools that make no state changes declare `readOnlyHint: true`. Default is `false`; missing annotation is a miss.
- [ ] `[UNIVERSAL]` **`destructiveHint` set to `false` on additive writes** — e.g. `SubmitFeedback` is additive, not destructive.
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
- [ ] `[OPINIONATED]` **`[posture]` prefix consistent** — if the project uses `[primary]` / `[secondary/helper]` prefix, it's applied to all tools without exception.

---

## 5. Parameter Schemas

- [ ] * `[UNIVERSAL]` **No nested objects** — parameters are flat top-level primitives. No `filters: dict`, no `options: object`. Use prefixed flat names instead (`filter_from`, `filter_status`).
- [ ] `[UNIVERSAL]` **Enums over free strings** — closed value sets use `Literal` / `enum`, not free `str`.
- [ ] `[UNIVERSAL]` **Optional parameters have sensible defaults** — optional means meaningful behaviour without the argument, not "nullable required".
- [ ] `[STACK:Python]` **Python parameters self-document where needed** — FastMCP/Pydantic tools use `Annotated` + `Field(description=..., pattern=..., examples=...)` for IDs, dates, limits, and ambiguous strings.
- [ ] `[EMPIRICAL]` **`anyOf`/null variants stripped** `[Claude Desktop, Claude Code ≥ 2.0.21]` — schemas with `anyOf: [T, null]` (typical when nullable/optional types in language SDKs serialize to JSON Schema) break Claude Desktop; top-level `anyOf` in `input_schema` causes a hard 400 in Claude Code ≥ 2.0.21. → Fix: `tool-design.md §Schema Compatibility Gotcha: anyOf with null`
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
- [ ] `[UNIVERSAL]` **Error messages are actionable** — every recoverable error includes an `Action:` hint or names a tool the agent can call next. "Entity not found — use ListDialogs to get valid IDs."
- [ ] `[UNIVERSAL]` **Generic backend errors preserve diagnostics** — "Bad Request", "Internal Server Error", or "not found" include safe field-level details, response excerpts, or correlation IDs; secrets are redacted.
- [ ] `[CONDITIONAL]` **Backend-unavailable errors explicit** — if the daemon/backend is down, the error message says so clearly ("daemon not running — start with: …"), not a raw socket exception.

---

## 8. Response Design

- [ ] `[UNIVERSAL]` **All list responses are bounded** — no tool returns unlimited results. Hard cap enforced. Message shown when results are truncated ("N more — use cursor X to continue").
- [ ] `[UNIVERSAL]` **Pagination tokens are opaque** — tokens encode enough state to reproduce the next page; agents don't need to parse them.
- [ ] `[UNIVERSAL]` **Pagination token validated on next call** — mismatch (wrong dialog, wrong context) returns explicit error, not silent wrong results.
- [ ] `[UNIVERSAL]` **Empty results distinguished from errors** — "no results" and "search failed" are different responses.
- [ ] `[OPINIONATED]` **Tabular text output is compact** — text `content` does not repeat large JSON; use compact tables/CSV previews while preserving required `structuredContent`.

---

## 9. Long-Running Operations

- [ ] `[UNIVERSAL]` **No blocking tools > a few seconds** — tools that invoke slow external APIs, file processing, or background sync use the async handle pattern (return task ID immediately, separate polling tool).
- [ ] `[UNIVERSAL]` **Handle pattern implemented correctly** — the first tool never blocks; it only enqueues and returns a handle.

---

## 10. Agent Feedback Channel

- [ ] * `[OPINIONATED]` **`SubmitFeedback` tool exists** — write-only, fire-and-forget, no read-back tool.
- [ ] `[OPINIONATED]` **`SubmitFeedback` description includes proactive triggers** — verbatim: when a tool returned unexpected output, error is unclear, capability was missing, behaviour contradicts docs.
- [ ] `[OPINIONATED]` **Operator CLI exists** — `feedback list`, `feedback status <id> <status>`, `feedback delete <id>`.
- [ ] `[OPINIONATED]` **Separate storage** — feedback persists in its own DB/file, not mixed with server's main data.

---

## 11. System Prompt (`server.instructions`)

- [ ] `[OPINIONATED]` **System prompt exists and is non-empty** — server has `server.instructions` set.
- [ ] `[OPINIONATED]` **Feedback directive present** — "Use SubmitFeedback immediately when a tool response is wrong, surprising, or missing a useful capability."
- [ ] `[OPINIONATED]` **Named workflow patterns (ALL-CAPS)** — at least one named pattern for the most common multi-step flow.
- [ ] `[OPINIONATED]` **Live state injected at startup** — connected account, active limits, or other runtime state built dynamically, not hardcoded at deploy time.
- [ ] `[OPINIONATED]` **Under 300 tokens** — estimate token count. Over budget = directive that should be moved into a tool description or a missing tool.

---

## 12. Transport and Logging

- [ ] * `[UNIVERSAL]` **No HTTP+SSE transport (2024-11-05)** — deprecated. Only `stdio` or Streamable HTTP.
- [ ] * `[CONDITIONAL]` **All logging goes to `stderr`** — for stdio servers, no `print()` or logger writing to `stdout`. Any `stdout` output corrupts the transport silently.
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

- [ ] `[UNIVERSAL]` **Untrusted content delimited in responses** — message bodies, file contents, DB rows wrapped in explicit framing, not injected raw into tool output.
- [ ] `[UNIVERSAL]` **Tools that fetch external content flagged in descriptions** — agents know to treat results as data, not instructions.
- [ ] * `[UNIVERSAL]` **Inputs validated at system boundary** — paths, shell arguments, URLs, tenant IDs, and command flags are allowlisted/normalised before use.
- [ ] `[UNIVERSAL]` **Secrets never leak** — tokens, cookies, API keys, OAuth codes absent from URLs, logs, tool responses, and feedback records.
- [ ] `[UNIVERSAL]` **Local server not exposed on public interface** — binds to `127.0.0.1` or Unix socket, or has authentication if network-accessible.
- [ ] `[CONDITIONAL]` **Origin header validation for Streamable HTTP** — server rejects requests with invalid `Origin` (HTTP 403). Usually handled by SDK — verify it's not disabled.

---

## 15. Testing

- [ ] `[UNIVERSAL]` **Integration smoke test exists** — calls every tool through the actual transport against a live server. Unit tests alone don't cover transport or schema serialisation.
- [ ] `[OPINIONATED]` **Dark-room UX test done at least once** — agent given the server with no briefing, asked to complete a real task, feedback queue reviewed. If not done: mark as debt. → Protocol: `agent-ux.md §Dark-Room Agent UX Testing`

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
