# MCP Tool Design Reference

> **Load when:** Naming, classifying, or writing descriptions for MCP tools; designing
> parameter schemas; deciding how many tools a server should expose.

---

## Three Primitives

MCP defines three distinct server primitives. Always use the right one.

| Primitive | Who decides to use it | Nature | Examples |
|-----------|----------------------|--------|---------|
| **Tool** | The model | Active — has side effects or retrieves dynamic data | `SearchMessages`, `SubmitFeedback` |
| **Resource** | The application/client | Passive — context data the client selects and injects | Current file, user profile, config snapshot |
| **Prompt** | The user | Reusable template the user invokes by name | "Summarise unread", "Draft a reply" |

If the model decides when to call it — Tool. If it's stable, addressable context an app pre-loads — Resource. If the user triggers it explicitly — Prompt.

Most servers start tools-only. Add Resources when you have stable URI-addressable data. Add Prompts when you find yourself writing the same system-prompt boilerplate repeatedly.

---

## Naming

**Convention:** `PascalCase`, verb-noun.

```
GetEntityInfo      ListDialogs       SubmitFeedback
MarkDialogForSync  SearchMessages    GetSyncStatus
```

**Rules:**
- Verb first (`Get`, `List`, `Search`, `Submit`, `Mark`, `Create`, `Delete`)
- Nouns are domain concepts, not implementation artifacts (`Dialog` not `Row`)
- Avoid generic names: `GetData`, `RunQuery` — useless to the LLM
- Watch for namespace collisions with the client: `GetMe` was intercepted by Claude Desktop as a meta-operation → renamed `GetMyAccount`

**Convention note:** the spec also allows `snake_case` and `service.action` notation. `PascalCase` is unambiguous in the Claude ecosystem; `snake_case` is equally valid if your SDK or team convention favours it. Pick one and be consistent.

**`title` field: mandatory.** Separate from `name` and `description`. Client UIs display it where the user sees tool activity — Claude Desktop shows it in the tool list and in "Claude is using tool…" blocks.

Without `title`, clients fall back to the raw `name` — and raw names are internal identifiers, not user-facing text.

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

Target ≤12 primary tools. Past that, ask what can be merged or promoted to a parameter.

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

**Caveat:** annotations are hints, not contracts. A client MUST NOT treat them as security controls — a server can declare any values. Set them accurately; never use them to bypass client safety checks.

---

## Writing Tool Descriptions

The description is a **prompt read by the LLM**. Answer three questions:

1. **When should I call this?** — proactive triggers, not just reactive ones
2. **What does it do?** — one sentence, mechanically accurate
3. **What should I not do with it?** — constraints, misuse patterns

**Example — SubmitFeedback:**

> Send feedback to the maintainer — bugs, confusing behaviour, or improvement suggestions.
> Use this **proactively** whenever you notice a tool response is unhelpful, surprising, or
> wrong; when an error message is unclear; or when a missing capability would have helped.
> Submissions are fire-and-forget — there is no follow-up, no tracking ID, and no read
> access for agents.

"Use this proactively" is a directive. Without it, agents wait to be asked.

**For parameters:** explain field semantics in the description, not just in the schema. The LLM reads the description; the schema is for validation.

---

## Structured Output — Prefer Schemas Over Text

**Default to structured output.** When a tool returns machine-parseable data (a list of entities, a status object, metadata), declare an `outputSchema` on the tool and return `structuredContent` alongside the text.

Agents can validate against the schema, extract fields reliably without parsing, and clients can render typed data directly. Text-only puts parsing burden on the agent and introduces brittleness.

**Spec requirement:** when `outputSchema` is declared, the server MUST return `structuredContent` conforming to it on every successful call — not just when convenient. A tool that declares a schema but conditionally returns text-only violates the protocol.

**Use `outputSchema` when:**
- Returning a list of objects
- Returning a status or metadata object
- The agent will need to extract specific fields from the response

**Text-only is fine for:**
- Free-form summaries, narratives, explanations
- Error messages and confirmations
- Content the agent reads but doesn't structurally process

The `content` text field should be a human-readable summary of the same data carried in
`structuredContent`. This redundancy is intentional — older clients that don't understand
`structuredContent` fall back to reading the text block. It's a compatibility bridge, not
documentation.

---

## Parameter Schema Design

- Enum values over free strings wherever the set is closed
- Optional truly optional: sensible default, meaningful behaviour without it
- Validate early at the tool layer; don't let invalid input reach the domain layer
- Strip/normalise strings at validation time (trim whitespace)
- `min_length=1` does **not** reject `"   "` — add an explicit nonempty check

### Schema Compatibility Gotcha: `anyOf` with null

`Optional[T]` in Pydantic v2 serialises to `{"anyOf": [{"type": "T"}, {"type": "null"}]}`. Several MCP clients reject this:

| Client | Symptom |
|--------|---------|
| Claude Desktop | Validation error — optional param treated as required, fails with "not valid under any of the given schemas" |
| Claude Code ≥ 2.0.21 | Hard 400 if `anyOf` appears at **top level** of `input_schema` |

**Fix 1 — Drop `Optional`, use bare default (simplest, most portable):**

```python
# Breaks Claude Desktop — generates anyOf: [int, null]:
from typing import Optional
param: Optional[int] = None

# Works everywhere — generates {type: integer}, field absent from required[]:
param: int = None
```

mypy/pyright warn about the second form. Add `# type: ignore` or use Fix 2 for cleaner types.

**Fix 2 — `SkipJsonSchema[None]` (type-checker clean):**

```python
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

def _drop_null(s: dict) -> None:
    s.pop("default", None)  # strips leaked "default": null from schema

class ToolInput(BaseModel):
    project_id: int | SkipJsonSchema[None] = Field(default=None, json_schema_extra=_drop_null)
    tags: list[str] | SkipJsonSchema[None] = Field(default=None, json_schema_extra=_drop_null)
```

`SkipJsonSchema[None]` removes the null arm; the callable drops the leaked `"default": null`. Verify with `ToolInput.model_json_schema()` — some older Pydantic v2 releases had a bug where `SkipJsonSchema` silently did nothing.

**Fix 3 — Post-process schema (nuclear, for legacy/third-party models):**

```python
import copy

def flatten_nullable(schema: dict) -> dict:
    schema = copy.deepcopy(schema)
    def _walk(node: dict) -> dict:
        if "anyOf" in node:
            non_null = [s for s in node["anyOf"] if s != {"type": "null"}]
            if len(non_null) == 1:
                merged = non_null[0]
                merged.update({k: v for k, v in node.items() if k != "anyOf"})
                return _walk(merged)
        return {k: (_walk(v) if isinstance(v, dict) else v) for k, v in node.items()}
    return _walk(schema)

clean_schema = flatten_nullable(MyModel.model_json_schema())
```

**FastMCP note:** FastMCP does **not** strip `anyOf: null` automatically — this fix is your responsibility even when using FastMCP. See `references/fastmcp-notes.md`.

### Argument Flattening

Avoid nested objects in parameter schemas. LLMs hallucinate the key names inside nested
objects — especially two or more levels deep.

```python
# Weak — model invents key names inside the dict
def list_messages(filters: dict) -> str: ...

# Strong — flat primitives, closed enum, nothing to invent
def list_messages(
    from_user: str | None = None,
    status: Literal["unread", "all"] = "all",
    limit: int = 20,
) -> str: ...
```

When parameters are logically grouped, use prefixed flat names (`filter_from`, `filter_status`)
over a nested `filter` object. Models fill in known top-level names with confidence; they guess
at nested ones.

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
"Entity 12345 not found — use ListDialogs to find valid dialog ids."
```

Include an `Action:` hint whenever the error is recoverable. When the backend is unavailable, say so explicitly — the agent needs to know it's an infrastructure problem, not a logic error.

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
For anything slow (file analysis, data migration, external API with high latency), use an
async handle pattern instead of blocking:

1. Tool returns immediately with a task `id` and `status: "working"`
2. A separate polling tool (`GetTaskStatus`, `CheckJobResult`) takes the `id` and returns current state
3. Final state returns the actual result or error

This requires no spec feature — just two tools and a server-side state store. The key invariant:
the first tool never blocks; it only enqueues work and returns a handle.

**When blocking is fine:** sub-second operations, anything where the LLM would retry anyway.
**When to use the handle pattern:** external API calls with unpredictable latency, file processing,
background sync, anything that's caused connection timeouts in practice.

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

If your server conditionally exposes tools (e.g., different tools before and after auth, or based
on runtime feature flags), declare the `listChanged` capability and emit the
`notifications/tools/list_changed` notification whenever the set changes.

```python
# capabilities declaration
{"tools": {"listChanged": True}}

# emit after tool set changes
await session.send_tool_list_changed()
```

Without this, clients cache the initial tool list and never learn about changes. For static
tool sets (the common case) this capability is irrelevant — skip it.
