# FastMCP Specifics

> **Load when:** Building or auditing an MCP server with the FastMCP framework (Python).
> Skip entirely if using the raw MCP Python SDK or another language.

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

## What FastMCP Does NOT Handle

**`anyOf: [T, null]` from `Optional[T]` — not stripped automatically.**

A common assumption is that FastMCP cleans up the Pydantic `Optional[T]` → `anyOf: [T, null]` serialisation before exposing the schema. It does not (FastMCP issues #2040, #2153). FastMCP emits standard Pydantic v2 schemas; Claude Desktop rejects `anyOf` null variants. The fix is your responsibility even when using FastMCP.

→ Concrete recipes: `python-notes.md §anyOf: [T, null]`

---

## PascalCase Tool Names

Python functions are `snake_case`; MCP tool names should be `PascalCase`. Use the `name=` parameter — the Python function name is never exposed to clients when `name=` is set:

```python
@mcp.tool(name="ListDialogs")
async def list_dialogs(limit: int = 20) -> list[dict]:
    """Lists available dialogs."""
    ...
```

Full decorator signature (FastMCP ≥ 2.x):

```python
@mcp.tool(
    name="CreateDocument",
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

---

## FastMCP-Specific Gotchas

**`compress_schema` silently strips `additionalProperties: false`**

FastMCP's internal schema compression (`prune_additional_properties=True` by default) removes `additionalProperties: false`. Currently no public config knob to disable — known bug (#3008).

**`structured_output=False` to opt out of auto-inference**

When return types are complex or you want full manual control, pass `structured_output=False` in the `@mcp.tool` decorator to suppress FastMCP's outputSchema inference. Pair with `output_schema={...}` to provide your own.

→ Other Python/Pydantic-level gotchas (Optional/required, complex return types, $schema header): `python-notes.md`
