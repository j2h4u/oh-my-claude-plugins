# MCP Tool Design Reference

> Load when naming/classifying tools, writing descriptions, designing parameter schemas, or sizing the tool surface. Mostly UNIVERSAL; tool-count thresholds and primary/secondary classification are OPINIONATED — protocol MUSTs are called out inline.

---

## Picking a Primitive — Tool, Resource, or Prompt

MCP defines three distinct server primitives. Always use the right one.

| Primitive | Who decides to use it | Nature | Examples |
|-----------|----------------------|--------|---------|
| **Tool** | The model | Active — has side effects or retrieves dynamic data | `search_messages`, `submit_feedback` |
| **Resource** | The application/client | Passive — context data the client selects and injects | Current file, user profile, config snapshot |
| **Prompt** | The user | Reusable template the user invokes by name | "Summarise unread", "Draft a reply" |

**Decision tree** (walk top-to-bottom; first matching branch wins):

1. **Does the model decide *when* to call it (mid-conversation, based on its own judgement)?** → **Tool**
2. **Does the user invoke it explicitly by name (slash command, picker)?** → **Prompt**
3. **Does it mutate state or have side effects?** → **Tool**
4. **Is it static reference content the client can pre-load per session (file, schema, profile)?** → **Resource**
5. **Otherwise** (dynamic data the model fetches on demand) → **Tool**

**One-line worked examples:**

| Primitive | Example | Why this primitive |
|-----------|---------|--------------------|
| Tool | `search_messages(query="invoice")` | Model decides when to search; result is dynamic. |
| Tool | `mark_dialog_for_sync(dialog_id=42)` | Mutates server state. |
| Resource | `@profile://current-user` | Stable per session, client pre-loads at startup. |
| Resource | `@github:issue://123` | URI-addressable static reference, user/app selects. |
| Prompt | `/draft-reply` slash command | User invokes explicitly by name; reusable template. |

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

**Pattern:** `^[a-z0-9_]{1,64}$` (snake_case + underscores for namespacing). Spec allows more (hyphens, dots, 128 chars); ecosystem uses this narrower form — match it.

**Namespacing in multi-server environments:** prefix the service — `asana_search`, `jira_issue_get`. Prefix before verb (LLMs scan domain-first when picking between servers).

**`title` field — set on every tool. `[OPINIONATED]`** Both audiences receive the full Tool definition (name, title, description, annotations), but clients that render a "Claude is using…" UI string surface `title` to humans verbatim while agents anchor selection on `name` + `description`. Without `title`, the UI falls back to the raw `name` (`ozon_search`, `GetMyRecentActivity`) — internal leakage.

Format: 1–3 words, product language, sentence case (`"Search Ozon"`, `"Recent activity"`, `"Sync status"`). Not a reformatted `name`. **Client surfacing varies** — Claude Desktop renders the "Claude is using …" string; Claude Code does not surface tool calls with that exact wording. Skip when no client in your matrix renders `title` distinctly from `name`.

---

## Tool Classification — Primary vs Secondary and the 10-Tool Signal

Tools ship in two tiers.

| Tier | When to use | Visibility |
|------|-------------|------------|
| `primary` | User-facing capability, the LLM should know it exists | Listed in tool catalogue |
| `secondary` / `helper` | Supporting operation, plumbing | May be hidden from catalogue |

**≤10 primary tools.** `[OPINIONATED]` More tools dilute LLM selection accuracy — every loaded tool description taxes the context window, even tools the agent never calls. Keep primary tools to ≤10.

Evidence: GitHub Copilot trimmed 40 default tools to 13, +2–5pp success / −400ms latency ([GitHub Blog, Nov 19 2025](https://github.blog/ai-and-ml/github-copilot/how-were-making-github-copilot-smarter-with-fewer-tools/)).

Before adding a tool: can two tools merge? Can a tool be promoted to a parameter? Past ≤10, answer those questions first.

---

## Annotations

Four tool annotations. All default to worst-case — declare explicitly whenever you can do better.

| Annotation | Default | Declare explicitly when |
|------------|---------|------------------------|
| `readOnlyHint` | `false` | Tool makes no state changes → set `true` |
| `destructiveHint` | `true` | Write is purely additive → set `false`. **Only meaningful when `readOnlyHint: false`** — read-only tools have no destructive semantics. |
| `idempotentHint` | `false` | Same args → same result, safe to retry → set `true` |
| `openWorldHint` | `true` | Tool is local-only, no external services → set `false` |

Clients use annotations to drive confirmation dialogs, auto-approval policies, and orchestrator trust decisions. Hints, not contracts — a client MUST NOT treat them as security controls (a server can declare any value). Set accurately; do not use to bypass client safety checks.

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

**Use `outputSchema` when:**
- Returning a list of objects
- Returning a status or metadata object
- The agent will need to extract specific fields from the response

**Text-only is fine for:**
- Free-form summaries, narratives, explanations
- Error messages and confirmations
- Content the agent reads but doesn't structurally process

**Contract:** declaring `outputSchema` makes `structuredContent` MUST on every successful call. Spec also marks the text `content` block SHOULD; **treat it as MUST in your code** — older clients and some SDK versions only read the text path. Including both is the safe default.

**Token economy for tabular data:** don't repeat large JSON blobs in the text `content`. For
read-only tabular results, make `content` a compact preview such as CSV or a short table, while
keeping the full machine-readable data in `structuredContent` when an `outputSchema` is declared.
If a tool needs a text export mode, use a small enum such as `response_format: "compact" | "json"`
or `response_format: "csv" | "json"` and document which formats are intended for humans versus
programmatic extraction. Never omit required `structuredContent` just to save tokens.

### Full example

→ [`examples/structured-output-search-orders.md`](../examples/structured-output-search-orders.md) — full tool definition + matching response, showing the canonical shape (`outputSchema` + `structuredContent` + compact text preview + all four annotations).

---

## Parameter Schema Design

- Enum values over free strings wherever the set is closed
- Optional truly optional: sensible default, meaningful behaviour without it
- Validate early at the tool layer; don't let invalid input reach the domain layer
- Strip/normalise strings at validation time (trim whitespace)
- `min_length=1` does **not** reject `"   "` — add an explicit nonempty check

### Schema Compatibility Gotcha: `anyOf` with null

**Scope: `inputSchema`.** Claude Desktop (and some other clients) reject `inputSchema` where an optional parameter is exposed as `{"anyOf": [{"type": "T"}, {"type": "null"}]}`. Fix: strip the null variant, collapse single-non-null `anyOf` to the bare type, drop `"default": null`.

```json
// broken
{ "name": "limit", "schema": { "anyOf": [{"type":"integer"},{"type":"null"}], "default": null } }

// fixed
{ "name": "limit", "schema": { "type": "integer", "default": 20 } }
```

**`outputSchema` nullable fields appear to be safe** as `{"type": ["string", "null"]}` (used in [`examples/structured-output-search-orders.md`](../examples/structured-output-search-orders.md)) — `inputSchema` validation runs on the client at call-dispatch time, but `outputSchema` is the server's contract for what it emits; clients don't reject the schema itself. Empirically untested across the matrix — probe before relying on it for a new target client.

**SDK shortcut:** FastMCP / Python `mcp` strips the null arm from `inputSchema` automatically since **v2.13.0** — don't hand-patch on newer versions. TypeScript SDK and others: verify per version (the official `@modelcontextprotocol/sdk-typescript` does not auto-strip as of skill-verified versions; build your own helper or post-process the Tool descriptor). Related FastMCP gotcha: `compress_schema` stripped `additionalProperties: false` from **both** input- and output-schemas until **v2.14.6** — upgrade or pass `prune_additional_properties=False`.

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

Typed nested models at ≤1 level deep are fine when `properties` is fully declared. Never two levels — hallucination reliably appears regardless of typing. For small groups (≤3 fields) prefer prefixed flat names (`filter_from`, `filter_status`) over a nested object.

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

**Choose by expected p95 duration** (not best case — clients abort on the long tail):

| p95 duration | Pattern | Notes |
|--------------|---------|-------|
| < 2 s        | Synchronous | Most read tools fall here. No special handling. |
| 2–20 s       | Synchronous, with a timeout-warning note in the description | Watch the client's tool-call timeout — see [clients.md](clients.md). Some hosts abort at 30 s; some users abort sooner. |
| 20 s – 2 min | `taskSupport: "optional"` if any target client supports Tasks; else roll-your-own handle | `optional` keeps synchronous fallback working. Roll-your-own = submit tool returns a handle + separate polling tool. |
| > 2 min      | `taskSupport: "required"` once your target clients negotiate `tasks` at `initialize`; until then, roll-your-own handle | Synchronous calls will be aborted by client timeouts. Marking `required` on a client that doesn't support Tasks breaks the tool — verify the [clients.md cross-client matrix](clients.md#cross-client-capability-matrix) first. |

There are two ways to expose the non-synchronous patterns. **Prefer the spec primitive when the
client supports it; fall back to the roll-your-own pattern when it doesn't.**

### Spec primitive — Tasks ([SEP-1686](https://modelcontextprotocol.io/community/seps/1686-tasks))

Two declarations: top-level `tasks` capability at `initialize` + per-tool `execution.taskSupport` (`forbidden` default | `optional` | `required`). Status today is owned by [clients.md](clients.md) — check before shipping. Wire shape + server-side invariants: [`examples/long-running-tasks-wire-shape.md`](../examples/long-running-tasks-wire-shape.md).

### Fallback — roll-your-own async handle

The default today (no tracked client negotiates `tasks`). Submit tool returns immediately with a domain `id` and `status: "working"`; a separate polling tool (`get_task_status`, `check_job_result`) returns current state until terminal. Same invariant as the spec primitive: the submit tool never blocks. Pattern leaks polling cadence into prompt engineering and depends on the agent calling the status tool — switch to the spec primitive once target clients support it. Full recipe: [`examples/long-running-tasks-wire-shape.md` §Roll-your-own](../examples/long-running-tasks-wire-shape.md#roll-your-own-fallback-use-today).

### When blocking is fine

Sub-second operations, anything where the LLM would retry anyway. Watch the client's tool-call
timeout — see [clients.md](clients.md) for empirical numbers per host.

---

## When to Split or Merge a Tool

Split when:
- Two modes have different descriptions/triggers
- One mode is read-only, the other writes
- The parameter changes the return shape significantly

Merge when:
- The modes are the same operation with a filter (`show_deleted=true`)
- Both modes have identical triggers and the same return shape

---

## Dynamic Tool Sets — `listChanged`

Declare `"tools": {"listChanged": true}` **only if the tool set actually mutates after init** (auth gating, feature flags, multi-tenant). Static surfaces declaring it mislead defenders into watching for events that never fire. When declared, emit `notifications/tools/list_changed` on every change — **but don't depend on delivery**: Claude Desktop drops it ([clients.md](clients.md)). If a tool must be present for a flow to succeed, register it from the start; treat the notification as audit-trail hygiene only ([security-threats.md §8](security-threats.md)).
