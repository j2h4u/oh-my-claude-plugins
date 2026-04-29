# MCP Server Audit Checklist

> **Load when:** Auditing an existing MCP server against skill guidelines.
>
> **How to use:** Go through each section. For each item mark `✅ pass`, `❌ fail`, or `— N/A`.
> Collect all `❌` items into a findings list at the end with the fix required.
> Items marked with `*` are high-priority — fix before anything else.

---

## 1. Design Philosophy

- [ ] * **Tool count ≤ 15** — count all tools exposed in the registry. If > 15, the surface needs consolidation or splitting into domain-specific servers.
- [ ] * **No thin API wrapper** — for each tool, ask: "does this map 1:1 to a backend endpoint?" If yes, it should bundle the downstream calls internally instead.
- [ ] * **Outcome orientation** — each tool name describes a user goal, not an operation. "TrackLatestOrder", not "GetOrderStatus".
- [ ] **One server, one job** — can you describe the server's purpose in one sentence? If not, scope is too broad.
- [ ] **80/20 check** — are there tools nobody calls? Review call logs or feedback queue. Dead tools should be removed.

---

## 2. Tool Naming and Classification

- [ ] **`snake_case` verb_noun names** — e.g. `list_dialogs`, `get_entity_info`, `submit_feedback`. No `getData`, `RunQuery`, `handle_request` (too generic), no spaces or special chars. Characters: `^[a-zA-Z0-9_]{1,64}$` — what Claude's frontend validates.
- [ ] * **`title` field set on every tool** — 1–3 words, in the product's language, sentence case, user-facing. Claude Desktop shows this in "Claude is using…" blocks and the tool list. Without it the raw `name` is shown (`ozon_search`, `GetMyRecentActivity`) which leaks internal naming to users. Not a reformatted `name` — write what a user would say: "Search Ozon", "Recent activity", "Sync status".
- [ ] **Primary/secondary classification consistent** — primary tools are user-facing capabilities; secondary/helper tools are plumbing. No primary tool that's implementation detail.
- [ ] **No namespace collision risk** — tool names don't collide with well-known client meta-operations (e.g. `GetMe` → `GetMyAccount`).

---

## 3. Tool Annotations

- [ ] **`readOnlyHint` set on read-only tools** — tools that make no state changes declare `readOnlyHint: true`. Default is `false`; missing annotation is a miss.
- [ ] **`destructiveHint` set to `false` on additive writes** — e.g. `SubmitFeedback` is additive, not destructive.
- [ ] **`idempotentHint` set where applicable** — tools safe to retry (same args → same result) declare it.
- [ ] **`openWorldHint: false` on local-only tools** — tools that don't touch external services should not carry the default `true`.

---

## 4. Tool Descriptions

- [ ] * **LLM-oriented** — descriptions answer: "When should I call this?", "What does it do?", "What should I NOT do with it?" Not just a one-line summary.
- [ ] **Proactive triggers** — descriptions say "Use proactively when…" for tools that agents should call without being asked.
- [ ] **Parameter semantics in prose** — field meanings explained in description, not just in schema. The LLM reads descriptions; schema is for validation.
- [ ] **`[posture]` prefix consistent** — if the project uses `[primary]` / `[secondary/helper]` prefix, it's applied to all tools without exception.

---

## 5. Parameter Schemas

- [ ] * **No nested objects** — parameters are flat top-level primitives. No `filters: dict`, no `options: object`. Use prefixed flat names instead (`filter_from`, `filter_status`).
- [ ] **Enums over free strings** — closed value sets use `Literal` / `enum`, not free `str`.
- [ ] **Optional parameters have sensible defaults** — optional means meaningful behaviour without the argument, not "nullable required".
- [ ] **`anyOf`/null variants stripped** `[Claude Desktop, Claude Code ≥ 2.0.21]` — schemas with `anyOf: [T, null]` (typical when nullable/optional types in language SDKs serialize to JSON Schema) break Claude Desktop; top-level `anyOf` in `input_schema` causes a hard 400 in Claude Code ≥ 2.0.21. → Fix: `tool-design.md §Schema Compatibility Gotcha: anyOf with null`
- [ ] **`min_length=1` is not enough** — whitespace-only strings checked explicitly; `"   "` passes `min_length=1`.

---

## 6. Structured Output

- [ ] **`outputSchema` declared on structured tools** — tools returning lists, status objects, or metadata have `outputSchema` defined.
- [ ] * **`structuredContent` returned on every successful call** — if `outputSchema` is declared, `structuredContent` MUST be present every time, not conditionally.
- [ ] **Text `content` present alongside `structuredContent`** — backwards-compat for older clients. Text is a human-readable summary of the same data, not a repeat of the raw JSON.

---

## 7. Error Handling

- [ ] * **Business errors use `isError: true`** — validation failures, API failures, entity-not-found — all returned as tool results with `isError: true`, not raised as exceptions.
- [ ] **Protocol errors reserved for protocol failures** — JSON-RPC exceptions only for malformed requests, unknown tool names. Not for domain errors.
- [ ] **Error messages are actionable** — every recoverable error includes an `Action:` hint or names a tool the agent can call next. "Entity not found — use ListDialogs to get valid IDs."
- [ ] **Backend-unavailable errors explicit** — if the daemon/backend is down, the error message says so clearly ("daemon not running — start with: …"), not a raw socket exception.

---

## 8. Response Design

- [ ] **All list responses are bounded** — no tool returns unlimited results. Hard cap enforced. Message shown when results are truncated ("N more — use cursor X to continue").
- [ ] **Pagination tokens are opaque** — tokens encode enough state to reproduce the next page; agents don't need to parse them.
- [ ] **Pagination token validated on next call** — mismatch (wrong dialog, wrong context) returns explicit error, not silent wrong results.
- [ ] **Empty results distinguished from errors** — "no results" and "search failed" are different responses.

---

## 9. Long-Running Operations

- [ ] **No blocking tools > a few seconds** — tools that invoke slow external APIs, file processing, or background sync use the async handle pattern (return task ID immediately, separate polling tool).
- [ ] **Handle pattern implemented correctly** — the first tool never blocks; it only enqueues and returns a handle.

---

## 10. Agent Feedback Channel

- [ ] * **`SubmitFeedback` tool exists** — write-only, fire-and-forget, no read-back tool.
- [ ] **`SubmitFeedback` description includes proactive triggers** — verbatim: when a tool returned unexpected output, error is unclear, capability was missing, behaviour contradicts docs.
- [ ] **Operator CLI exists** — `feedback list`, `feedback status <id> <status>`, `feedback delete <id>`.
- [ ] **Separate storage** — feedback persists in its own DB/file, not mixed with server's main data.

---

## 11. System Prompt (`server.instructions`)

- [ ] **System prompt exists and is non-empty** — server has `server.instructions` set.
- [ ] **Feedback directive present** — "Use SubmitFeedback immediately when a tool response is wrong, surprising, or missing a useful capability."
- [ ] **Named workflow patterns (ALL-CAPS)** — at least one named pattern for the most common multi-step flow.
- [ ] **Live state injected at startup** — connected account, active limits, or other runtime state built dynamically, not hardcoded at deploy time.
- [ ] **Under 300 tokens** — estimate token count. Over budget = directive that should be moved into a tool description or a missing tool.

---

## 12. Transport and Logging

- [ ] * **No HTTP+SSE transport (2024-11-05)** — deprecated. Only `stdio` or Streamable HTTP.
- [ ] * **All logging goes to `stderr`** — no `print()` or logger writing to `stdout`. Any `stdout` output corrupts the stdio transport silently.
- [ ] **Transport matches deployment** — `stdio` for subprocess clients (Claude Desktop), Streamable HTTP for inter-container or HTTP-capable clients.

---

## 13. Architecture (Daemon/Stateless split — if applicable)

> **Skip if:** single-process server without a persistent background resource (DB, WebSocket, ML model, Unix socket). All items below are N/A for stateless servers.

- [ ] **Stale socket file cleaned at daemon startup** — daemon deletes existing socket file before `bind()`, otherwise crashes with "address already in use" after unclean shutdown.
- [ ] **MCP server reads stdin until client closes** — not exiting after first response. Premature exit silently breaks stdio sessions.
- [ ] **Daemon-not-running error is user-facing** — `FileNotFoundError` / `ConnectionRefusedError` translated to a single actionable message, not leaked as a socket exception.
- [ ] **Crash isolation** — MCP server crash doesn't kill the daemon; daemon crash returns clean error on every tool call rather than crashing the MCP server.

---

## 14. Security

- [ ] **Untrusted content delimited in responses** — message bodies, file contents, DB rows wrapped in explicit framing, not injected raw into tool output.
- [ ] **Tools that fetch external content flagged in descriptions** — agents know to treat results as data, not instructions.
- [ ] **Local server not exposed on public interface** — binds to `127.0.0.1` or Unix socket, or has authentication if network-accessible.
- [ ] **Origin header validation for Streamable HTTP** — server rejects requests with invalid `Origin` (HTTP 403). Usually handled by SDK — verify it's not disabled.

---

## 15. Testing

- [ ] **Integration smoke test exists** — calls every tool through the actual transport against a live server. Unit tests alone don't cover transport or schema serialisation.
- [ ] **Dark-room UX test done at least once** — agent given the server with no briefing, asked to complete a real task, feedback queue reviewed. If not done: mark as debt. → Protocol: `agent-ux.md §Dark-Room Agent UX Testing`

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

Items marked `*` that failed → HIGH by default.
