# MCP Design Philosophy — Not an API Wrapper

> **Load when:** designing the overall tool surface for a new MCP server, or reviewing whether an existing surface is well-shaped for agent consumption.
> **Scope:** UNIVERSAL.

---

## Design for agents, not developers

A good REST API is not a good MCP server. REST endpoints assume a human writes the orchestration; MCP tools must *be* the orchestration. Map endpoints 1:1 → tool pollution (every loaded description taxes the context window) + choreography burden (agent reconstructs intent from low-level primitives) + transactionality breaks (call 2 of 3 fails, no recovery path).

Block's Linear server: 30+ tools → 2 tools across three iterations, performance improving at each step. The failure mode is a cliff, not a slope.

---

## One tool, one goal

**Bad** — mirrors three REST endpoints:

```python
get_user_by_email(email)
list_orders_for_user(user_id)
get_order_status(order_id)
```

**Good** — one user-level goal, orchestration inside the tool:

```python
track_latest_order(email: str) -> str
# internally calls /users, /orders, /shipments
# returns: "Order #12345 shipped via FedEx, arriving Thursday."
```

The agent makes one call; the context window sees one tool name.

---

## Rules

- **80/20:** 20% of API capabilities serve 80% of user requests. Expose that 20% from real workflows; the rest does not justify tool explosion.
- **≤10 primary tools per server** is a signal (see [tool-design.md §Classification](tool-design.md#classification)). Past it, split into domain-specific servers — never cram to avoid the split. *One server, one job.*
- **Bundle, don't expose.** Multiple API calls + filtering + normalisation belong inside the tool. That complexity is the point, not a smell.
- **Curate ruthlessly.** Every tool added taxes every agent that loads the server. Merging tools that serve the same goal beats splitting them by implementation detail. A single tool with a filter parameter beats two tools with different return shapes.
- **Tools, descriptions, errors are prompt engineering** — not documentation. The agent reads descriptions to decide what to call; error messages are observations it self-corrects on.
- **MCP server = BFF for agents.** Aggregate upstream calls; shape responses for how the agent consumes them, not how the underlying API returns them.

---

## Concrete comparisons

| Domain | Bad (wrapper) | Good (outcome) |
|--------|--------------|----------------|
| E-commerce | `get_user`, `list_orders`, `get_status` (3 calls) | `track_latest_order(email)` (1 call) |
| Support | `list_responses → get_response → get_messages` | `triage_request(response_id)` |
| Email | Raw `payload.body.data` (base64 MIME) | `search_emails(query)` → `{subject, sender, snippet}` |
| Task tracker | 30+ GraphQL query tools | `execute_query(query, category)` (routing inside) |

---

## `server.instructions` — agent orientation block

Returned in the `initialize` response. Agent reads it once at session start; not re-sent on tool calls. Keep it tight: domain authority, named workflows, stable context hints, feedback directive — nothing that belongs in a tool description or response payload.

Canonical shape + format rules + budget principle live in [agent-ux.md §System Prompt as Configuration Surface](agent-ux.md#system-prompt-as-configuration-surface). Omit `server.instructions` entirely when there is nothing domain-specific to say.
