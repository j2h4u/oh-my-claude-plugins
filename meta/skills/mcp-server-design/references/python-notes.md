# Python / Pydantic Notes

> **Load when:** Building or auditing an MCP server in Python — either with the raw
> MCP Python SDK or with FastMCP. Skip if using another language.

This reference collects Python-ecosystem implementation specifics. Abstract design
principles live in `tool-design.md`; framework-specific behavior for FastMCP lives
in `fastmcp-notes.md`.

---

## `anyOf: [T, null]` — Concrete Fixes for Pydantic v2

Pydantic v2 serialises `Optional[T]` (and `T | None`) as `{"anyOf": [{"type": "T"}, {"type": "null"}]}`. Multiple MCP clients reject this — see `tool-design.md §Schema Compatibility Gotcha: anyOf with null` for the abstract problem and client matrix.

Three working fixes, in order of preference:

### Fix 1 — Drop `Optional`, use bare default (simplest, most portable)

```python
# Breaks Claude Desktop — generates anyOf: [int, null]:
from typing import Optional
param: Optional[int] = None

# Works everywhere — generates {type: integer}, field absent from required[]:
param: int = None
```

mypy/pyright warn about the second form. Add `# type: ignore` per-line or use Fix 2 for clean types.

### Fix 2 — `SkipJsonSchema[None]` (type-checker clean)

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

### Fix 3 — Post-process schema (nuclear, for legacy/third-party models)

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

---

## Other Pydantic v2 / Python SDK Gotchas

**`Optional[param]` without `= None` ends up in `required[]`**

`param: Optional[str]` with no default is put in `required[]` — the Python MCP SDK determines "required" from defaults, not type annotations (issue #1402). Always pair `Optional[X]` or `X | None` with `= None`.

**Complex return types crash schema generation**

Tools returning third-party objects (`pandas.DataFrame`, `sqlalchemy.Row`, etc.) crash on `outputSchema` inference because Pydantic can't generate a schema for them. Solutions:
- Annotate return as `dict` and serialize manually
- Hand-write the `output_schema` (FastMCP supports this) or skip structured output entirely
- Wrap the object in a Pydantic model that defines the shape you actually want to expose

**`$schema` field rejected by Gemini**

Pydantic emits a top-level `"$schema"` URL on `model_json_schema()`. Gemini's API rejects it with a 400. If targeting Gemini: `schema.pop("$schema", None)` before exposing.

**`null` inside string `enum` arrays**

Pydantic can generate `{"type": "string", "enum": ["a", "b", null]}` for `Literal["a", "b"] | None`. This violates JSON Schema (the `null` literal inside a string-typed enum is invalid). Fix with the `anyOf` recipes above (eliminate the null branch entirely) or accept `anyOf: [{enum: [...]}, {type: null}]`.

**Logging to stdout corrupts stdio transport**

Python's default `print()` and `logging.basicConfig()` write to `stdout`. With stdio transport, this corrupts the JSON-RPC stream silently. Always configure logging to `stderr`:

```python
import logging, sys
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
```
