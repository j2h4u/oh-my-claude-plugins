# Worked example — `search_orders` (structured output)

> Load when implementing a read tool with `outputSchema` + `structuredContent`. Demonstrates the canonical shape: typed structured payload + compact human-readable preview in `content`. Rules behind the shape live in [tool-design.md §Structured Output](../references/tool-design.md#structured-output--prefer-schemas-over-text).

## Tool definition

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

## Matching tool response

```json
{
  "structuredContent": {
    "orders": [
      { "id": "ORD-8821", "status": "shipped",   "total_usd": 59.99, "tracking_number": "1Z999AA10123456784" },
      { "id": "ORD-8734", "status": "delivered",  "total_usd": 24.50, "tracking_number": "1Z999AA10123456001" }
    ],
    "total": 2
  },
  "content": [{ "type": "text", "text": "2 orders: ORD-8821 (shipped, $59.99, tracking 1Z999AA10123456784); ORD-8734 (delivered, $24.50, tracking 1Z999AA10123456001)." }]
}
```

## What to copy

- `additionalProperties: false` on every nested object in both schemas.
- All four annotations declared explicitly — `destructiveHint: false` is the load-bearing opt-out.
- `content[0].text` is a compact human-readable preview, **not** a JSON dump of `structuredContent` (token economy — see [tool-design.md](../references/tool-design.md#structured-output--prefer-schemas-over-text)).
- Nullable field (`tracking_number`) uses `["string", "null"]` in `outputSchema`. Output schemas are server-emitted (client doesn't validate inbound the way it gates inputs), so the `anyOf:[T,null]` input-schema rejection observed on some clients hasn't been seen here — but coverage is thin; probe your target client before relying ([tool-design.md §Schema Compatibility](../references/tool-design.md#schema-compatibility-gotcha-anyof-with-null)).
