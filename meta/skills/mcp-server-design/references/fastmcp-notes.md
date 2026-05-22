# FastMCP Specifics

> **Load when:** Building or auditing an MCP server with the FastMCP framework (Python).
> Skip entirely if using the raw MCP Python SDK or another language.
>
> **Scope:** STACK-SPECIFIC: FastMCP. Do not treat FastMCP behaviours as generic MCP SDK
> behaviour.

This file covers framework-specific behavior of FastMCP only. For Pydantic-level
concerns that apply equally to the raw MCP Python SDK (anyOf null, complex return
types, required[] inference, $schema header), see `python-notes.md`.

---

## What FastMCP Handles Automatically

| Concern | FastMCP behavior |
|---------|-----------------|
| `$ref` / `$defs` dereferencing | Automatic (`dereference_schemas=True` by default). Fixes VS Code Copilot and other clients that can't resolve JSON Schema `$ref` inline. Opt out: `FastMCP("name", dereference_schemas=False)` |
| `outputSchema` generation | Auto-inferred from return type annotation. `-> list[dict]` → schema from Pydantic. `-> str` → wrapped as `{"type": "object", "properties": {"result": {"type": "string"}}, "x-fastmcp-wrap-result": true}` |
| Exceptions → `isError` | Unhandled exceptions become MCP error responses automatically — no manual `isError: true` wiring needed |
| Input coercion | Pydantic validation with coercion by default: `"10"` → `10`, `"true"` → `True`. Strict opt-in: `FastMCP("name", strict_input_validation=True)` |

---

## `anyOf: [T, null]` from `Optional[T]` — fixed in v2.13.0

**Historical issue (≤ v2.12.x):** FastMCP emitted raw Pydantic v2 `Optional[T]` → `anyOf: [T, null]` schemas without cleanup. Claude Desktop rejected these. Issue #2040, closed 2025-10-14.

**Current behavior (v2.13.0+):** PR #2073 (commit `e036cba`, merged 2025-10-14) shipped Pydantic-compatible input validation as the new default. Released in v2.13.0 "Cache Me If You Can" (2025-11-15): <https://github.com/PrefectHQ/fastmcp/releases/tag/v2.13.0>. The `anyOf: [T, null]` rejection no longer applies.

FastMCP also exposes a Pydantic validation toggle (added in v2.13.0 via PR #2073). The table above shows `strict_input_validation=True` as the strict opt-in — but that exact flag name was not confirmed in release notes. Verify against current <https://gofastmcp.com> docs before relying on the flag name. The capability is real; the option name needs a check.

**v3.x note:** Latest stable is **v3.3.1** (2026-05-15). Repo moved `jlowin/fastmcp` → `PrefectHQ/fastmcp` with v3.0. PyPI + import path unchanged. v3.0 introduces provider/transform architecture (`FileSystemProvider`, `OpenAPIProvider`, `ProxyProvider`, `SkillsProvider`), `ResourcesAsTools`/`PromptsAsTools` adapters, component versioning (`@tool(version="2.0")`), session state (`ctx.set_state()`/`get_state()`), tool timeouts, MCP-compliant pagination, and `--reload` dev mode. For anything beyond v2.x patterns, point at the v3 release notes and <https://gofastmcp.com>.

→ If hitting schema rejection on v2.12.x or older: `python-notes.md §anyOf: [T, null]`

---

## Tool Names in FastMCP

Python function names are `snake_case`, and MCP tool names should also be `snake_case` — so the default FastMCP behaviour (function name = tool name) is already correct. No `name=` override needed in the common case:

```python
@mcp.tool()
async def list_dialogs(limit: int = 20) -> list[dict]:
    """Lists available dialogs."""
    ...
# → exposes tool name "list_dialogs" ✓
```

Use `name=` only when you need to override: disambiguating a collision, wrapping a legacy API, or fitting a specific naming constraint:

```python
@mcp.tool(name="search_messages_v2")  # versioning, legacy compat, etc.
async def search_messages(...): ...
```

Full decorator signature (FastMCP ≥ 2.x):

```python
@mcp.tool(
    name="create_document",            # override only if needed
    description="...",                 # overrides docstring if provided
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
    output_schema={...},               # explicit outputSchema, overrides inferred
    structured_output=False,           # suppress structured output inference
)
async def create_document(...): ...
```

Docstrings become tool descriptions unless `description=` is passed explicitly. For tools with
non-obvious output, include a short response-shape note in the docstring or explicit description:
main fields, units, truncation, and whether the text response is a compact preview of structured
data. Keep long static reference material in MCP Resources, not in every tool docstring.

---

## FastMCP-Specific Gotchas

**`compress_schema` silently strips `additionalProperties: false` — fixed in v2.14.6**

Bug existed in v2.14.4–v2.14.5: FastMCP's internal schema compression (`prune_additional_properties=True` by default) removed `additionalProperties: false`, breaking MCP client compatibility. User-visible failure: `Invalid schema for function ...: 'additionalProperties' is required to be supplied and to be false`. Issue #3008 (<https://github.com/PrefectHQ/fastmcp/issues/3008>), PR #3102 (<https://github.com/PrefectHQ/fastmcp/pull/3102>), merged 2026-02-06.

**Fix shipped in v2.14.6** (2026-03-27) and all v3.x releases. If pinned to v2.14.5 or older, pass the flag explicitly: `compress_schema(schema, prune_additional_properties=False)`.

**`structured_output=False` to opt out of auto-inference**

When return types are complex or you want full manual control, pass `structured_output=False` in the `@mcp.tool` decorator to suppress FastMCP's outputSchema inference. Pair with `output_schema={...}` to provide your own.

→ Other Python/Pydantic-level gotchas (Optional/required, complex return types, $schema header): `python-notes.md`
