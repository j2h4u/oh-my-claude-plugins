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

If the model decides when to call it — Tool. If it's stable, addressable context an app pre-loads — Resource. If the user triggers it explicitly — Prompt.

Most servers start tools-only. Add Resources when you have stable URI-addressable data. Add Prompts when you find yourself writing the same system-prompt boilerplate repeatedly.

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

**Case:** snake_case. The spec is permissive about casing; the ecosystem (GitHub official MCP, all reference implementations) is uniform on snake_case — match it.

**Character set:** The MCP spec (2025-11-25) says tool names SHOULD be 1–128 chars, matching `^[A-Za-z0-9_\-.]{1,128}$` — this is SHOULD, not MUST. No client tracked in [clients.md](clients.md) is known to narrow the spec range. Convention pattern: `^[a-z0-9_]{1,64}$` (snake_case, underscores for word breaks and prefix namespacing — `asana_search`, `jira_issue_get`). Hyphens and dots are spec-allowed but vanishingly rare in the ecosystem — prefer underscores for namespacing. Source: [Tools spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

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

## Tool Classification — Primary vs Secondary and the 10-Tool Signal

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

| Annotation | Default | Declare explicitly when |
|------------|---------|------------------------|
| `readOnlyHint` | `false` | Tool makes no state changes → set `true` |
| `destructiveHint` | `true` | Write is purely additive → set `false`. **Only meaningful when `readOnlyHint: false`** — read-only tools have no destructive semantics. |
| `idempotentHint` | `false` | Same args → same result, safe to retry → set `true` |
| `openWorldHint` | `true` | Tool is local-only, no external services → set `false` |

Clients use annotations to drive confirmation dialogs, auto-approval policies, and orchestrator trust decisions.

> Schema defaults: `readOnlyHint=false`, `destructiveHint=true` (when not read-only), `idempotentHint=false`, `openWorldHint=true`. Source: https://modelcontextprotocol.io/specification/2025-11-25/schema

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

**Spec rule** (2025-11-25): when `outputSchema` is declared, `structuredContent` conforming to it is **MUST** on every successful call; a text `content` block is **SHOULD** (backwards-compat). A tool that declares a schema and returns text-only violates the protocol. Source: [Tools spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

**Pragmatic rule — promote SHOULD to MUST in your code: always return both.** Some SDK/client combinations reject responses missing the text `content` block; older clients that don't understand `structuredContent` only read the text block. Behaviour drifts by SDK version (Python `mcp`/FastMCP and `@modelcontextprotocol/sdk-typescript` have both changed handling across releases) — `verify against your target SDK version + client matrix in `clients.md` before relying on `structuredContent`-only`. Including both is the safe default.

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

Several MCP clients reject schemas where an optional parameter is exposed as `{"anyOf": [{"type": "T"}, {"type": "null"}]}`:

| Client | Symptom |
|--------|---------|
| Claude Desktop | Validation error — optional param treated as required, fails with "not valid under any of the given schemas" |
| Some MCP clients | Reject schemas where `anyOf` appears at the top level of `input_schema`. Test against your target clients; the matrix moves version-to-version. |

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

Apply the fix at schema generation time using your SDK's idioms.

**SDK status (2026-05):**
- **FastMCP / Python `mcp`** — fixed in **FastMCP v2.13.0** (2025-11-15) via PR #2073; Pydantic-compatible input validation strips the `null` arm automatically. **If you're on ≥ v2.13.0, do not hand-patch — the SDK already emits a clean schema.** ≤ v2.12.x: hand-patch required.
- **`@modelcontextprotocol/sdk-typescript`** — verify against your version; behaviour drifts release-to-release.
- **Other SDKs / raw schema construction** — assume no auto-strip; apply the fix above.

**Related FastMCP gotcha — `additionalProperties: false` stripped by `compress_schema`:** issue [#3008](https://github.com/PrefectHQ/fastmcp/issues/3008), fixed in **v2.14.6** (2026-03-27). Symptom: `Invalid schema for function ...: 'additionalProperties' is required to be supplied and to be false`. ≤ v2.14.5: pass `prune_additional_properties=False` to `compress_schema` explicitly. ≥ v2.14.6: no action.

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

**Choose by expected p95 duration** (not best case — clients abort on the long tail):

| p95 duration | Pattern | Notes |
|--------------|---------|-------|
| < 2 s        | Synchronous | Most read tools fall here. No special handling. |
| 2–20 s       | Synchronous, with a timeout-warning note in the description | Watch the client's tool-call timeout — see [clients.md](clients.md). Some hosts abort at 30 s; some users abort sooner. |
| 20 s – 2 min | `taskSupport: "optional"` if any target client supports Tasks; else roll-your-own handle | `optional` keeps synchronous fallback working. Roll-your-own = submit tool returns a handle + separate polling tool. |
| > 2 min      | `taskSupport: "required"` once your target clients negotiate `tasks` at `initialize`; until then, roll-your-own handle | Synchronous calls will be aborted by client timeouts. Marking `required` on a client that doesn't support Tasks breaks the tool — verify the [clients.md cross-client matrix](clients.md#cross-client-capability-matrix) first. |

There are two ways to expose the non-synchronous patterns. **Prefer the spec primitive when the
client supports it; fall back to the roll-your-own pattern when it doesn't.**

### Spec primitive — Tasks (spec **2025-11-25**, experimental, [SEP-1686](https://modelcontextprotocol.io/community/seps/1686-tasks))

> ⚠️ **As of 2026-05, no client tracked in [clients.md](clients.md) has confirmed Tasks support, and the major SDKs (`mcp`/FastMCP, `@modelcontextprotocol/sdk-typescript`) do not yet expose first-class registration helpers for the wire shapes below — they may need to be hand-emitted in the capabilities/tool payload. Use the roll-your-own pattern below as the default today; treat this section as future-leaning. Verify the cross-client matrix and your SDK version before shipping.**

The spec adds a first-class task primitive that augments `tools/call` (and `sampling/createMessage`, `elicitation/create`). **Two declarations are required** — top-level `tasks` capability at `initialize`, plus per-tool intent via `execution.taskSupport` (`forbidden` default | `optional` | `required`).

→ Full wire shape (`initialize` payload, per-tool declaration, `tools/call` augmentation, `tasks/get` / `tasks/result` / `tasks/cancel` polling): [`examples/long-running-tasks-wire-shape.md`](../examples/long-running-tasks-wire-shape.md). Server-side invariants (ID generation, `ttl` shortening, polling-only contract, session binding) live there too.

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

**Client delivery is not guaranteed.** Claude Desktop is documented in [clients.md](clients.md) as likely dropping `list_changed` notifications. Treat the emission as hygiene (defenders/auditors watch for it on a mutating surface — see [security-threats.md §8](security-threats.md)), not as the mechanism your correctness depends on. If a tool must be present for a flow to succeed, declare it from the start instead of relying on a post-init update arriving.
