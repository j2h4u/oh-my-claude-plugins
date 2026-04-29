# FastMCP Specifics

> **Load when:** Building or auditing an MCP server with the FastMCP framework (Python).
> Skip entirely if using the raw MCP Python SDK.

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

This is a known open issue (FastMCP issues #2040, #2153). FastMCP emits standard Pydantic v2 schemas; Claude Desktop rejects `anyOf` null variants. You must apply the fix yourself.

→ See `tool-design.md §Schema Compatibility Gotcha: anyOf with null` for three concrete fixes.

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

## Known Gotchas

**`Optional[param]` without `= None` ends up in `required[]`**

`param: Optional[str]` with no default is put in `required[]` — the SDK determines "required" from defaults, not type annotations. Always pair `Optional[X]` or `X | None` with `= None`.

**Complex return types crash schema generation**

Tools returning third-party objects (`pandas.DataFrame`, `sqlalchemy.Row`, etc.) will crash on `outputSchema` inference. Solutions:
- Annotate return as `dict` and serialize manually
- Use `structured_output=False` in the decorator
- Use `output_schema={...}` with a hand-written schema

**`compress_schema` silently strips `additionalProperties: false`**

FastMCP's internal schema compression (`prune_additional_properties=True` by default) removes `additionalProperties: false`. Currently no public config knob to disable — known bug (#3008).
