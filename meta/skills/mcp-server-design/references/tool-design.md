# MCP Tool Design Reference

> **Load when:** Naming, classifying, or writing descriptions for MCP tools; designing
> parameter schemas; deciding how many tools a server should expose.
>
> **Scope:** mostly UNIVERSAL. Tool-count thresholds and primary/secondary classification are
> opinionated heuristics; protocol requirements are called out explicitly.

---

## Three Primitives

MCP defines three distinct server primitives. Always use the right one.

| Primitive | Who decides to use it | Nature | Examples |
|-----------|----------------------|--------|---------|
| **Tool** | The model | Active — has side effects or retrieves dynamic data | `search_messages`, `submit_feedback` |
| **Resource** | The application/client | Passive — context data the client selects and injects | Current file, user profile, config snapshot |
| **Prompt** | The user | Reusable template the user invokes by name | "Summarise unread", "Draft a reply" |

If the model decides when to call it — Tool. If it's stable, addressable context an app pre-loads — Resource. If the user triggers it explicitly — Prompt.

Most servers start tools-only. Add Resources when you have stable URI-addressable data. Add Prompts when you find yourself writing the same system-prompt boilerplate repeatedly.

---

## Naming

**Convention:** `snake_case`, verb_noun.

```
get_entity_info      list_dialogs       submit_feedback
mark_dialog_for_sync  search_messages    get_sync_status
```

**Rules:**
- Verb first (`get_`, `list_`, `search_`, `submit_`, `create_`, `delete_`)
- Nouns are domain concepts, not implementation artifacts (`dialog` not `row`)
- Avoid generic names: `get_data`, `run_query` — useless to the LLM
- Watch for namespace collisions with the client: `get_me` intercepted by some clients → use `get_my_account`

**Why snake_case:** the spec (2025-11-25) is permissive about casing, but snake_case is the established convention — GitHub's official MCP server, all official reference implementations, and the broader ecosystem follow it. Claude Desktop agents treat non-snake_case as inconsistent with ecosystem norms. PascalCase is essentially absent in practice.

**Character set — spec vs. clients:** The MCP spec (2025-11-25) says tool names SHOULD be 1–128 chars, limited to `[A-Za-z0-9_\-.]` — this is SHOULD, not MUST. The spec's range is more permissive than what most deployed clients enforce. Cross-client safe pattern: `^[a-zA-Z0-9_-]{1,64}$` (snake_case base with hyphens for namespacing). For client-specific enforcement details (Claude Desktop, Claude Frontend Remote MCP), see [clients.md](clients.md). Source: [Tools spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

**Namespacing by service/resource** (multi-server environments): prefix with service name — `asana_search`, `jira_search`, `asana_projects_search`. Prefer prefix over suffix — the prefix establishes domain context before the verb, which aligns with how LLMs scan tool lists when selecting among multiple servers.

**`title` field: OPTIONAL per spec, but include it.** `[OPINIONATED]` Spec marks `title` as optional. In practice: humans see `title` in Claude Desktop UI (tool list, "Claude is using…" blocks); agents see `name`. Both audiences need different framing — `name` is an internal identifier optimized for LLM selection, `title` is user-facing prose. Without `title`, clients fall back to the raw `name`. Source: [Tools spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

```
name:  "ozon_search"          →  Claude Desktop shows: "Claude is using tool ozon_search"  ← bad
title: "Search Ozon"          →  Claude Desktop shows: "Claude is using Search Ozon"       ← good

name:  "GetMyRecentActivity"  →  Claude Desktop shows: "Claude is using tool GetMyRecentActivity"  ← bad
title: "Recent activity"      →  Claude Desktop shows: "Claude is using Recent activity"           ← good
```

**Format:** 1–3 words, in the language of the product, user-facing. Sentence case (first word capitalised, rest lowercase). A short verb phrase or noun phrase that describes what the tool does from the user's perspective — not what it does technically.

Do not write `title: "Get My Recent Activity"` (just a reformatted `name`). Write what a user would naturally say: "Recent activity", "Search messages", "Sync status".

---

## Classification

Tools ship in two tiers.

| Tier | When to use | Visibility |
|------|-------------|------------|
| `primary` | User-facing capability, the LLM should know it exists | Listed in tool catalogue |
| `secondary` / `helper` | Supporting operation, plumbing | May be hidden from catalogue |

**≤10 primary tools.** `[OPINIONATED]` More tools dilute LLM selection accuracy — every loaded tool description taxes the context window, even tools the agent never calls. Keep primary tools to ≤10.

Primary evidence: GitHub Copilot trimmed its default 40 built-in tools to 13 core tools, gaining +2–5 pp success rate on SWE-Lancer/SWEbench-Verified and cutting −400ms latency in A/B. Their MCP server alone exposes 93 tools at ~55k tokens before any user input — they route around this with embedding-guided clustering. Source: [GitHub Blog, Nov 19 2025](https://github.blog/ai-and-ml/github-copilot/how-were-making-github-copilot-smarter-with-fewer-tools/).

Before adding a tool: can two tools merge? Can a tool be promoted to a parameter? Past ≤10, answer those questions first.

---

## Annotations

Four tool annotations. All default to worst-case — declare explicitly whenever you can do better.

| Annotation | Default | Set to `true` when |
|------------|---------|-------------------|
| `readOnlyHint` | `false` | Tool makes no state changes |
| `destructiveHint` | `true` | Tool's write is destructive — set `false` for purely additive writes |
| `idempotentHint` | `false` | Same args → same result, safe to retry |
| `openWorldHint` | `true` | Tool touches external services — set `false` for local-only operations |

Clients use annotations to drive confirmation dialogs, auto-approval policies, and orchestrator trust decisions.

> Defaults from MCP schema reference: `readOnlyHint=false`, `destructiveHint=true` (when not read-only), `idempotentHint=false`, `openWorldHint=true`. Pessimistic-by-default: unannotated tools are treated as most-dangerous. Hints are advisory, not security boundaries. Source: https://modelcontextprotocol.io/specification/2025-11-25/schema

**Caveat:** annotations are hints, not contracts. A client MUST NOT treat them as security controls — a server can declare any values. Set them accurately; never use them to bypass client safety checks.

---

## Safe Defaults for Mutating Tools

Any tool that can spend money, publish content, change permissions, delete data, or trigger
external side effects must default to the least-surprising safe state.

Examples:
- Create campaigns, jobs, alerts, or automations as `paused`, `draft`, or `disabled`
- Prefer `dry_run: true` or preview tools before irreversible execution
- Require explicit activation for destructive or costly actions (`activate=true`, separate
  `activate_campaign`, or a confirmation token from a prior preview)
- Set conservative limits by default: small batch sizes, rate limits, no "all tenants" scope

Do not hide dangerous defaults behind documentation. Put the safety into the implementation and
make the tool description state the default clearly.

---

## Writing Tool Descriptions

<!-- canonical owner: "tools-are-prompts (how)" — the "why" rationale lives in agent-ux.md -->

The description is a **prompt read by the LLM**. Answer three questions:

1. **When should I call this?** — proactive triggers, not just reactive ones
2. **What does it do?** — one sentence, mechanically accurate
3. **What should I not do with it?** — constraints, misuse patterns

**Example — `submit_feedback`:**

> Send feedback to the maintainer — bugs, confusing behaviour, or improvement suggestions.
> Use this **proactively** whenever you notice a tool response is unhelpful, surprising, or
> wrong; when an error message is unclear; or when a missing capability would have helped.
> Submissions are fire-and-forget — there is no follow-up, no tracking ID, and no read
> access for agents.

"Use this proactively" is a directive. Without it, agents wait to be asked.

**For parameters:** explain field semantics in the description, not just in the schema. The LLM reads the description; the schema is for validation.

**For responses:** describe the shape the agent should expect, especially for non-trivial
structured output. Include the main fields, units, truncation behaviour, and whether the text
summary is a preview of `structuredContent`. If the server has static reference material such
as query-language fields, enum catalogs, or service limits, expose it as an MCP Resource instead
of stuffing it into every tool description.

---

## Structured Output — Prefer Schemas Over Text

<!-- canonical owner: "outputSchema → structuredContent" -->

**Default to structured output.** When a tool returns machine-parseable data (a list of entities, a status object, metadata), declare an `outputSchema` on the tool and return `structuredContent` alongside the text.

Agents can validate against the schema, extract fields reliably without parsing, and clients can render typed data directly. Text-only puts parsing burden on the agent and introduces brittleness.

**Spec requirement:** when `outputSchema` is declared, the server MUST return `structuredContent` conforming to it on every successful call — not just when convenient. A tool that declares a schema but conditionally returns text-only violates the protocol. Source: [Tools spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

**Use `outputSchema` when:**
- Returning a list of objects
- Returning a status or metadata object
- The agent will need to extract specific fields from the response

**Text-only is fine for:**
- Free-form summaries, narratives, explanations
- Error messages and confirmations
- Content the agent reads but doesn't structurally process

**When `outputSchema` is declared, always return BOTH:**
- `structuredContent` — the typed, machine-parseable payload conforming to the schema
- `text` (the `content` field) — a human-readable summary of the same data

This redundancy is intentional — older clients that don't understand `structuredContent` fall back to reading the text block. It's a compatibility bridge, not documentation. Per spec: `structuredContent` is MUST when `outputSchema` is declared; the text `content` block is SHOULD (backwards-compat). In practice, many SDKs reject responses without a text `content` block even though the spec is more permissive — always include both. A tool that declares a schema and returns text-only violates the protocol; `structuredContent` without text breaks legacy clients and most deployed SDKs.

**Token economy for tabular data:** don't repeat large JSON blobs in the text `content`. For
read-only tabular results, make `content` a compact preview such as CSV or a short table, while
keeping the full machine-readable data in `structuredContent` when an `outputSchema` is declared.
If a tool needs a text export mode, use a small enum such as `response_format: "compact" | "json"`
or `response_format: "csv" | "json"` and document which formats are intended for humans versus
programmatic extraction. Never omit required `structuredContent` just to save tokens.

### Full example

Tool definition:

```json
{
  "name": "search_orders",
  "title": "Search orders",
  "description": "Call when the user asks about their orders, order history, or shipment status. Searches orders by customer email and optional status filter. Returns a list of matching orders with id, status, total, and tracking number.",
  "inputSchema": {
    "type": "object",
    "required": ["email"],
    "additionalProperties": false,
    "properties": {
      "email":  { "type": "string", "description": "Customer email address to search by" },
      "status": { "type": "string", "enum": ["pending", "shipped", "delivered", "cancelled"], "description": "Filter to orders with this status; omit to return all statuses" },
      "limit":  { "type": "integer", "minimum": 1, "maximum": 50, "default": 10, "description": "Maximum number of orders to return" }
    }
  },
  "outputSchema": {
    "type": "object",
    "required": ["orders", "total"],
    "additionalProperties": false,
    "properties": {
      "orders": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["id", "status", "total_usd", "tracking_number"],
          "additionalProperties": false,
          "properties": {
            "id":             { "type": "string" },
            "status":         { "type": "string", "enum": ["pending", "shipped", "delivered", "cancelled"] },
            "total_usd":      { "type": "number" },
            "tracking_number":{ "type": ["string", "null"] }
          }
        }
      },
      "total": { "type": "integer", "description": "Total matching orders before limit" }
    }
  },
  "annotations": { "readOnlyHint": true, "destructiveHint": false, "idempotentHint": true, "openWorldHint": false }
}
```

Matching tool response:

```json
{
  "structuredContent": {
    "orders": [
      { "id": "ORD-8821", "status": "shipped",   "total_usd": 59.99, "tracking_number": "1Z999AA10123456784" },
      { "id": "ORD-8734", "status": "delivered",  "total_usd": 24.50, "tracking_number": "1Z999AA10123456001" }
    ],
    "total": 2
  },
  "content": [{ "type": "text", "text": "{\"orders\":[{\"id\":\"ORD-8821\",\"status\":\"shipped\",\"total_usd\":59.99,\"tracking_number\":\"1Z999AA10123456784\"},{\"id\":\"ORD-8734\",\"status\":\"delivered\",\"total_usd\":24.50,\"tracking_number\":\"1Z999AA10123456001\"}],\"total\":2}" }]
}
```

---

## Parameter Schema Design

- Enum values over free strings wherever the set is closed
- Optional truly optional: sensible default, meaningful behaviour without it
- Validate early at the tool layer; don't let invalid input reach the domain layer
- Strip/normalise strings at validation time (trim whitespace)
- `min_length=1` does **not** reject `"   "` — add an explicit nonempty check

### Schema Compatibility Gotcha: `anyOf` with null

Several MCP clients reject schemas where an optional parameter is exposed as `{"anyOf": [{"type": "T"}, {"type": "null"}]}`:

| Client | Symptom |
|--------|---------|
| Claude Desktop | Validation error — optional param treated as required, fails with "not valid under any of the given schemas" |
| Claude Code ≥ 2.0.21 | Hard 400 if `anyOf` appears at **top level** of `input_schema` |

This typically arises from how language SDKs serialise nullable/optional types into JSON Schema. The fix is conceptual: strip the null variant from `anyOf` before exposing the schema; collapse single-non-null `anyOf` to the bare type; drop `"default": null`. Apply at schema generation time when possible, or as a post-processing pass before constructing the `Tool` descriptor.

**Before (broken — Claude Desktop rejects this):**
```json
{
  "name": "limit",
  "schema": {
    "anyOf": [{"type": "integer"}, {"type": "null"}],
    "default": null
  }
}
```

**After (fixed — bare type, no null variant):**
```json
{
  "name": "limit",
  "schema": {
    "type": "integer",
    "default": 20
  }
}
```

→ **Python/Pydantic recipes**: `python-notes.md §anyOf: [T, null]`
→ **FastMCP behavior**: `fastmcp-notes.md` — does **not** auto-strip; the fix is your responsibility

### Argument Flattening

Avoid *untyped* nested objects — `dict`, bare `object` with no `properties`. These give the LLM no schema to anchor on, so it invents key names.

```python
# Weak — model invents key names inside the untyped dict
def list_messages(filters: dict) -> str: ...

# Strong — flat primitives, closed enum, nothing to invent
def list_messages(
    from_user: str | None = None,
    status: Literal["unread", "all"] = "all",
    limit: int = 20,
) -> str: ...
```

**Typed nested models at one level deep are fine** when the group is logically cohesive and the sub-schema fully declares `properties`. The failure mode is schema-less dicts, not typed sub-models.

Use prefixed flat names (`filter_from`, `filter_status`) instead of a nested object when the group is small (≤3 fields) or when you observe hallucination in practice. For larger, coherent parameter groups, a typed nested model with all fields declared is preferable to a long flat namespace. Never go two levels deep — that's where hallucination reliably appears regardless of typing.

---

## Error Handling

### `isError: true` vs. protocol errors

The spec separates two error paths:

- **Tool execution error** → return `isError: true` in the tool result. The LLM receives it and can self-correct. Use for: validation failures, API failures, business logic errors, anything the agent should see.
- **Protocol error** → JSON-RPC level. Use only for malformed requests (unknown tool name, invalid JSON-RPC structure).

Raising/throwing a protocol-level exception for a business error makes it opaque — the agent can't read it.

### Error message quality

Error messages should be actionable:

```
# Weak
"Entity not found"

# Strong
"Entity 12345 not found — use list_dialogs to find valid dialog ids."
```

Include an `Action:` hint whenever the error is recoverable. When the backend is unavailable, say so explicitly — the agent needs to know it's an infrastructure problem, not a logic error.

Preserve diagnostic detail. Generic backend errors like "Bad Request", "Internal Server Error",
or "not found" are not enough for an agent to self-correct. Include the backend's field-level
validation details, request correlation ID, and relevant response body excerpt where safe.
Do not truncate errors so aggressively that the cause disappears; do redact secrets, tokens,
cookies, and tenant-private data.

Note: what to record in server-side logs (including the "no raw args in logs" rule) is owned by `observability.md §What to record` — do not duplicate here.

---

## Response Design

**Lists:** always bound the response. Returning unlimited results crashes agent context.
- Hard cap + `"N more results not shown — use cursor X to continue"`
- Pagination token the agent passes back on next call

**Pagination token design:**
- Encode enough state to reproduce the next page independently
- Validate token belongs to the same context on next call — mismatch is an explicit error
- Make tokens opaque; the agent should not parse them

**Empty results:** distinguish `"no results"` from `"search failed"`.

---

## Long-Running Operations

Synchronous tools that block for more than a few seconds hold the connection and degrade UX.
For anything slow (file analysis, data migration, external API with high latency), do not block —
return a handle and let the client poll.

There are two ways to do this. **Prefer the spec primitive when the client supports it; fall
back to the roll-your-own pattern when it doesn't.**

### Spec primitive — Tasks (spec **2025-11-25**, experimental, [SEP-1686](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1686))

The spec adds a first-class task primitive that augments `tools/call` (and `sampling/createMessage`,
`elicitation/create`). Declare per-tool with `execution.taskSupport`:

```jsonc
{
  "name": "deep_research",
  "description": "...",
  "execution": { "taskSupport": "required" }  // "forbidden" | "optional" | "required"
}
```

| Value | Meaning |
|-------|---------|
| `forbidden` | Default. Tool is invoked synchronously; no task augmentation. |
| `optional` | Client may choose to augment with a task or call synchronously. |
| `required` | Client must augment with a task — synchronous call is rejected. |

Wire shape when the client augments:

```jsonc
// Client → server
{"method":"tools/call","params":{"name":"deep_research","arguments":{...},"task":{"ttl":600000}}}
// Server → client (immediate)
{"result":{"taskId":"...","status":"working","createdAt":"...","ttl":600000,"pollInterval":2000}}
// Client polls
{"method":"tasks/get","params":{"taskId":"..."}}
// Terminal: working | input_required | completed | failed | cancelled
{"method":"tasks/result","params":{"taskId":"..."}}  // returns the original CallToolResult
{"method":"tasks/cancel","params":{"taskId":"..."}}  // optional
```

Notes:
- The receiver generates the task ID and may shorten the requested `ttl`.
- Clients poll. `notifications/tasks/status` is optional — requestors must not rely on it.
- Bind tasks to the session / auth context; use high-entropy IDs.
- SDK support is rolling out — check [clients.md](clients.md) and your SDK's release notes before
  marking a tool `taskSupport: "required"`.

### Fallback — roll-your-own async handle

For clients that don't yet implement tasks, expose two tools:

1. Submit tool returns immediately with a domain `id` and `status: "working"`.
2. A separate polling tool (`get_task_status`, `check_job_result`) takes the `id` and returns current state.
3. Final state returns the actual result or error.

No spec feature needed — just two tools and a server-side state store. Same invariant: the first
tool never blocks; it only enqueues work and returns a handle. Prefer the spec primitive once your
target clients support it — the roll-your-own pattern leaks polling cadence into prompt engineering
and depends on the agent remembering to call the status tool.

### When blocking is fine

Sub-second operations, anything where the LLM would retry anyway. Watch the client's tool-call
timeout — see [clients.md](clients.md) for empirical numbers per host.

---

## One Tool, One Concern

Split when:
- Two modes have different descriptions/triggers
- One mode is read-only, the other writes
- The parameter changes the return shape significantly

Merge when:
- The modes are the same operation with a filter (`show_deleted=true`)
- Both modes have identical triggers and the same return shape

---

## Dynamic Tool Sets — `listChanged`

**Declare the `tools` capability whenever your server supports tools — it is MUST.** The `listChanged` flag on that capability is OPTIONAL. `"tools": {}` is valid for basic tool support; `"tools": {"listChanged": true}` additionally signals that the tool list can change at runtime. Source: [Tools spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

Only add `listChanged: true` if your tool list actually mutates after initialization (e.g., different tools before and after auth, feature-flag gating). If you declare it, the server SHOULD emit `notifications/tools/list_changed` whenever the set changes — otherwise clients cache the initial list and never learn about updates.

```python
# Basic tool support — always required when the server has tools
{"tools": {}}

# Dynamic tool support — only if your list mutates at runtime
{"tools": {"listChanged": True}}

# emit after tool set changes
await session.send_tool_list_changed()
```

Note: security-threats.md may recommend emitting `list_changed` on certain events (e.g., principal change); Claude Desktop is documented in clients.md as likely ignoring it. Declare `listChanged: true` only if the rest of your design depends on it being delivered.
