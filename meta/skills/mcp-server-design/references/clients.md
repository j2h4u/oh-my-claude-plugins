# MCP Client Compatibility Notes

> Load when client limitations affect server design. EMPIRICAL — compatibility notes, not protocol guarantees. Each row is dated; recheck periodically. `⚠️` = partial / needs probe.

---

## Cross-client capability matrix

> **Use:** pick the safe surface for a server targeting more than one client — the
> intersection of ✅ cells is what you can rely on. Per-client detail below.
> Source for the Claude Code column: `anthropics/claude-code` CHANGELOG.md, accessed 2026-05-22.

| Capability / Notification | Claude Desktop (2026-04-28) | Claude Code (v2.1.148, 2026-05-22) |
|---------------------------|------------------------------|-------------------------------------|
| Tools | ✅ | ✅ |
| Resources | ✅ | ✅ (`@server:proto://path` mention) |
| Prompts | ✅ | ✅ (`/mcp__<server>__<prompt>` slash) |
| `elicitation` (mid-call user input) | ❌ not declared | ✅ since v2.1.76 |
| `roots` | ❌ not declared | ⚠️ unverified |
| `sampling` (deprecated DRAFT-2026-v1) | ❌ + deprecated | ❌ + deprecated |
| `completions` | ❌ not declared | ⚠️ unverified |
| `notifications/tools/list_changed` | ⚠️ likely dropped | ✅ since v2.1.0 |
| `notifications/message` (logging → model) | ❌ silently dropped | ⚠️ unverified |
| `notifications/progress` | ❌ no `progressToken` sent | ⚠️ unverified |
| `tasks` (SEP-1686) | ⚠️ not observed in `initialize` | ⚠️ unverified |
| OAuth 2.1 for remote servers | n/a (subprocess client) | ✅ since v1.0.27 (RFC 9728 + dynamic client registration) |
| Tool-call timeout knob | ~20s defensive (single 26s observation) | `MCP_TOOL_TIMEOUT` env var, no default |
| Output budget | not published | `MAX_MCP_OUTPUT_TOKENS=25000`, warn at 10000 |

**Safe-surface rule when targeting both:** assume only the non-interactive subset works
(Tools, Resources, Prompts, `isError`, `server.instructions`, tool descriptions). Push
state through tool responses, not push notifications. Defer to async-handle pattern for
anything >20s.

---

## Claude Desktop

**Verified:** 2026-04-28 (empirical, mcp-server-ozon) | **Recheck:** ~2026-07-01

Source: MCP debug log (raw JSON-RPC frames) + `sendLoggingMessage` probes + direct agent questions.

---

`tools/list` is called on every new connection — dynamic tool descriptions work.

Capability statuses are in the cross-client matrix above; design implications below.

Notable Claude-Desktop-only signal: `io.modelcontextprotocol/ui` capability is declared (proprietary — likely HTML/React artefact rendering; does not affect tool UX).

---

### Server → Client Notifications

| Notification | Status | Details |
|---|---|---|
| `notifications/message` (logging) | ❌ Silently dropped | Transport delivers it; model never sees it. Agent confirmed it receives no log messages or progress. Do not use for progress reporting. |
| `notifications/progress` | ❌ Not functional | Claude Desktop does not include `progressToken` in `tools/call`'s inbound `_meta`, so server-emitted progress notifications have no recipient. Verified 2026-04-28. |
| `notifications/tools/list_changed` | ⚠️ UNVERIFIED | Likely dropped — no matching capability declared. |
| `notifications/resources/updated` | ⚠️ UNVERIFIED | Same assumption — likely dropped. |

**Practical rule:** do not rely on any server-push notification reaching the model. All communication to the model must go through tool responses, `isError` errors, tool descriptions, or `server.instructions`.

---

### Timeouts

- **Observed:** socket closed after ~26s in one LLM-enriched search operation (single data point on mcp-server-ozon, 2026-04-28 — not a spec limit and not a Desktop-published budget).
- **Operator-chosen safety margin:** plan for ≤20s end-to-end based on the single 26s observation. Anything longer carries cancellation risk on this client; until more data points exist, treat 20s as defensive guidance, not a documented limit.
- **After socket close:** server continues executing (lock held), but the result has nowhere to go.
- **On reconnect:** a new call finds the lock and receives the "server busy" message — agent sees this and can act on it.

---

### Reliable Communication Channels (server → model)

In order of reliability:

| Channel | Works? | When available |
|---------|--------|----------------|
| Tool response (`content`) | ✅ Always | On tool call completion |
| `isError: true` + error message | ✅ Always | On tool error (including "server busy") |
| `server.instructions` | ✅ Always | At `initialize` — once per session |
| Tool descriptions | ✅ Always | At `tools/list` — every connection |
| `notifications/message` | ❌ Dropped | — |
| `notifications/progress` | ⚠️ Unknown | Only if client sends `progressToken` |
| `elicitation/create` | ❌ Not supported | — |
| `sampling/createMessage` | ❌ Not supported, deprecated protocol-wide | — |

---

### Design Implications for Claude Desktop

**Tool call duration:**
- Target <20s. Anything longer risks connection drop.
- For slow operations: do not block. Roll-your-own async handle (Tasks not negotiated) — recipe in [tool-design.md §Long-Running Operations](tool-design.md).
- "Server busy" with remaining time estimate is visible to the agent — write informative busy messages.

**Tool names:**
- Watch for namespace collisions with client meta-operations. `get_me` was intercepted by Claude Desktop as a client-side operation → renamed `get_my_account`.

**All context must be in descriptions and system prompt:**
- Notifications don't work → schema, behaviour, limits, failure modes all belong in tool descriptions and `server.instructions`.
- Describe failure modes explicitly: "if session expired — do X", "if server busy — retry in N seconds".
- Describe tool dependencies: "call search_x before query_x".

**What NOT to implement for Claude Desktop:**
- Push progress notifications (model won't see them)
- `elicitation` mid-execution (not supported)
- `sampling/createMessage` (not supported, deprecated protocol-wide)
- Resource subscriptions (likely dropped, unverified)

---

## Claude Code

**Verified:** 2026-05-22 (v2.1.148) | **Recheck:** ~2026-08-01

Source: <https://code.claude.com/docs/en/mcp> and `anthropics/claude-code` CHANGELOG.md on `main`. Most agents reading this skill are running inside Claude Code — this section applies directly.

---

Capability statuses are in the cross-client matrix above; design implications below. Two Claude-Code-specific notes:

- **OAuth 2.1 (since v1.0.27)** — full RFC 9728 with dynamic client registration, plus a `headersHelper` script alternative for non-OAuth scenarios (see *Dynamic Headers* below).
- **`elicitation` works** — server can request structured mid-task user input via an interactive dialog.

---

### Resources and Prompts

- **Resources:** `@server:protocol://resource/path` mention syntax (e.g. `@github:issue://123`).
- **Prompts:** surfaced as slash commands `/mcp__<server>__<prompt>` (e.g. `/mcp__github__pr_review 456`).

---

### Timeouts and Output Limits

| Knob | Value | Design implication |
|------|-------|--------------------|
| `MCP_TOOL_TIMEOUT` | ms, no default | Operators set per-server; design slow tools to fit or use async-handle pattern. |
| `MAX_MCP_OUTPUT_TOKENS` | 25 000 default, warn at 10 000 | Paginate / compress before this; per-tool override via `anthropic/maxResultSizeChars` (≤ 500 KB). |

---

### Tool Loading and Scopes

| Knob | Values | Effect |
|------|--------|--------|
| `ENABLE_TOOL_SEARCH` | `true` / `false` / `auto` | Deferred tool loading — tools fetched on demand. `alwaysLoad: true` on a server exempts it. |
| Server scope | `local` (`~/.claude.json`) · `project` (`.mcp.json`, git-shared) · `user` (`~/.claude.json`, all projects) | Controls who sees the server config. |

---

### Tool Name Constraints

No stricter-than-spec enforcement observed. CHANGELOG references tool-name issues but none relate to character-set rejection beyond MCP spec. The spec range (`^[A-Za-z0-9_\-.]{1,128}$`) is what Claude Code accepts; the snake_case convention pattern lives in [tool-design.md §Naming](tool-design.md#naming).

---

### Dynamic Headers

`"headersHelper": "/path/to/script"` in `.mcp.json` invokes a script per request — use for token refresh or per-call signing when OAuth doesn't fit.

---

### Design Implications for Claude Code

- **Elicitation works** — servers can request additional user input mid-execution. Worth using over embedding all context in the tool description when optional parameters need clarification.
- **Dynamic tool lists work** — use `notifications/tools/list_changed` for servers that add/remove tools at runtime (feature flags, multi-tenant surfaces).
- **Output token budget is generous but finite** — 25 000 tokens default. For large payloads, use `anthropic/maxResultSizeChars` annotation on the tool definition. Compress or paginate before hitting the limit.
- **`MCP_TOOL_TIMEOUT` is the right knob for slow tools** — set it server-side in `.mcp.json` env block, not in tool logic.
- **Sampling: do not use** — no evidence of support, and the primitive is deprecated protocol-wide.
- **`claude mcp serve`** exposes Claude Code itself as an MCP server (stdio) — useful for agent-to-agent tool sharing.

---

## Cursor

Cursor is not covered in this skill — verify against [Cursor's MCP documentation](https://docs.cursor.com/context/model-context-protocol) before targeting it.

---

**Status legend** (used throughout this file):
- `❌` — confirmed absent / dropped as of verified date
- `⚠️` — partial or needs targeted check; subtext clarifies which
- `✅` — confirmed working as spec describes
