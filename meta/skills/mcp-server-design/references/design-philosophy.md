# MCP Design Philosophy — Not an API Wrapper

> **Load when:** Designing the overall tool surface for a new MCP server, or reviewing whether
> an existing server is well-shaped for agent consumption.

---

## MCP Is a UI for Agents

> "A good REST API is not a good MCP server." — philschmid.de
> "MCP is a User Interface for Agents. Different users, different design principles." — philschmid.de

The MCP transport works fine. Servers typically don't — because they are built like REST APIs.

REST was designed for human developers who read documentation once, write a sequential script,
debug it, and ship. Those same principles — small composable endpoints, CRUD verbs,
resource-per-URL — become actively harmful when LLMs are the consumer.

**Design for agents, not developers.** An MCP server is not an API client; it is an interface
layer that translates between agent intent and domain operations.

---

## The Thin-Wrapper Antipattern

**Don't do this:**

```python
# Bad: three tools mirroring three API endpoints
get_user_by_email(email)        # → GET /users?email=
list_orders_for_user(user_id)   # → GET /orders?user=
get_order_status(order_id)      # → GET /orders/{id}/status
```

What breaks:

- **Tool pollution** — the agent loads all tool descriptions on every request. Each tool taxes
  the context window, even tools that won't be called. Benchmarks across 6 LLMs showed accuracy
  dropping measurably as tool count rose; the GitHub MCP team found switching from 40 tools to
  3–10 yielded a 60–90% reduction in context window usage.
- **Choreography burden** — the agent must reconstruct intent from low-level primitives.
  Sequencing three calls across a conversation is error-prone reasoning, not domain logic.
- **Accuracy collapse** — Block's Linear server went from 30+ tools to 2 over three iterations,
  with performance improving at each step. The failure is a cliff, not a slope.
- **Transactionality breaks** — if call 2 of 3 fails, the agent has no recovery path and
  system state is inconsistent.

Named patterns for this antipattern: "The Full-API Trap", "Tool Pollution",
"The HTTP Client Trap", "Inference Burden."

> "If you take your REST or GraphQL service and replicate it for the MCP broker, what are you
> practically doing differently? The answer is simple — nothing." — nordicapis.com

---

## The Correct Model: One Tool, One Goal

> "MCP isn't about surfacing every possible endpoint, it's about teaching an agent what it can
> do, with what context, and to what end." — nordicapis.com

**Do this instead:**

```python
# Good: one tool, one user goal
track_latest_order(email: str) -> str
# internally calls /users, /orders, /shipments
# returns: "Order #12345 shipped via FedEx, arriving Thursday."
```

The orchestration (three API calls, joining the results, formatting the answer) happens inside
the tool. The agent makes one call. The context window sees one tool name.

The **80/20 rule:** 20% of API capabilities serve 80% of user requests. Identify that 20% from
real user workflows and expose only those. The remaining 80% of endpoints do not justify tool
explosion.

**Target:** 5–15 tools per server. Past 15, split into domain-specific servers — never cram
more tools into one server to avoid the split. "One server, one job."

> "Your 20-tool MCP server is making every agent that connects to it dumber." — ksopyla.com

---

## Design Principles

**1. Design for outcomes, not operations.**
Each tool should complete a user-level goal. Bundle the internal complexity — multiple API calls,
data filtering, normalisation — inside the tool. That complexity is the point, not a smell.

**2. MCP is the seam between reasoning and execution.**
The agent plans and re-plans (non-deterministic). Tools execute (deterministic). The MCP layer is
that boundary. Tools should validate inputs, execute reliably, and return machine-checkable
results. Don't push orchestration into the agent.

**3. Curate ruthlessly.**
Every tool added taxes every agent that loads the server. Prefer merging tools that serve the
same goal over splitting them by implementation detail. A tool that returns everything with a
filter parameter is better than two tools with different return shapes.

**4. Tools, descriptions, and errors are prompt engineering.**
> "Writing good tool descriptions is not documentation work, it is prompt engineering." — dev.to

The agent reads tool descriptions to decide what to call and when. Error messages are
observations the agent uses to self-correct. Neither is documentation; both are instructions.

**5. Treat the server like a Backend-for-Frontend for agents.**
The BFF pattern aggregates multiple service calls into a response shaped for a specific consumer.
Apply the same principle: shape each tool response for how an agent will consume it, not for how
the underlying API returns it.

---

## Concrete Comparisons

| Domain | Bad (wrapper) | Good (outcome) |
|--------|--------------|----------------|
| E-commerce | `get_user`, `list_orders`, `get_status` — 3 calls | `track_latest_order(email)` — 1 call, internal pipeline |
| Support | `list_responses → get_response → get_messages` | `triage_request(response_id)` — parallel internals, structured return |
| Email | Raw `payload.body.data` (base64 MIME blob) | `search_emails(query)` → flat `{subject, sender, snippet}` |
| Task tracker | 30+ GraphQL query tools | `execute_query(query, category)` — routing inside the tool |

---

## When Thin IS Correct

The above applies to tools that expose domain operations. The **daemon+stateless split**
(see SKILL.md) is a different kind of "thin" — the MCP server process stays thin (no state,
no resources) while the *tool implementation* does the orchestration. That split is correct
architecture; it doesn't contradict this philosophy.
