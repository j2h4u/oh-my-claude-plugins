# MCP Client Compatibility Notes

> **Load when:** Designing tools or server behaviour that may be affected by client limitations.
>
> **Scope:** EMPIRICAL. These are compatibility notes, not MCP protocol guarantees.
>
> **Format:** each limitation is dated — verify periodically whether it's been resolved.
> Items marked `⚠️ UNVERIFIED` need a targeted check before relying on them.

---

## Claude Desktop

**Verified:** 2026-04-28 (empirical, mcp-server-ozon) | **Recheck:** ~2026-07-01

Source: MCP debug log (raw JSON-RPC frames) + `sendLoggingMessage` probes + direct agent questions.

---

### Handshake

Claude Desktop sends on every connect:

```
Client → initialize  (protocolVersion: "2025-11-25")
Server ← result      (protocolVersion, capabilities, instructions)
Client → notifications/initialized
Client → tools/list
Server ← result      (tools array)
```

`tools/list` is called on **every new connection** — dynamic tool descriptions work.

---

### Capabilities Declared by Claude Desktop

| Capability | Status | Consequence for server |
|------------|--------|------------------------|
| `sampling` | ❌ NOT declared — ⚠️ Deprecated in DRAFT-2026-v1 (SEP-2596) | Server cannot call `sampling/createMessage`. Moot: capability not declared AND protocol-level deprecated. Do not design around sampling for new servers. |
| `elicitation` | ❌ NOT declared | Server cannot prompt the user mid-execution |
| `roots` | ❌ NOT declared | Server cannot request workspace root directories |
| `completions` | ❌ NOT declared | Parameter autocompletion not supported |
| `io.modelcontextprotocol/ui` | ✅ declared | Proprietary — likely HTML/React artefact rendering in UI. Does not affect tool UX. |
| `tasks` | ⚠️ UNVERIFIED — not observed in `initialize` response (2026-04-28) | Until probed and confirmed, assume Tasks (SEP-1686) is unsupported. Roll-your-own async handle for long-running operations — see §Design Implications. |

**Bottom line:** Claude Desktop does not declare the interactive server-to-client capabilities (sampling, elicitation, roots, completions). Tools, Resources, and Prompts still work — the surface is the non-interactive subset of MCP.

> **Sampling deprecation note:** As of DRAFT-2026-v1 (SEP-2596), sampling is formally deprecated protocol-wide with a 1-year support window and no named replacement. Source: [draft sampling spec](https://modelcontextprotocol.io/specification/draft/client/sampling). New servers must not design around sampling.

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
| `sampling/createMessage` | ❌ Not supported — ⚠️ Deprecated in DRAFT-2026-v1 (SEP-2596) | — |

---

### Design Implications for Claude Desktop

**Tool call duration:**
- Target <20s. Anything longer risks connection drop.
- For slow operations: do not block the call. Claude Desktop has not (as of 2026-04-28) been observed to declare the `tasks` capability — until a probe confirms otherwise, assume Tasks (SEP-1686) is unsupported and use the roll-your-own async-handle fallback (return `id` + `status: "working"` immediately, expose a separate polling tool for state). Canonical recipe and the spec-primitive alternative: [tool-design.md §Long-Running Operations](tool-design.md).
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
- `sampling/createMessage` (not supported, and deprecated protocol-wide in DRAFT-2026-v1 — SEP-2596)
- Resource subscriptions (likely dropped, unverified)

---

### Open Questions (to verify)

- **`io.modelcontextprotocol/ui`:** what exactly can the server return to trigger HTML rendering? Tool response with specific MIME type?
- **Timeout precision:** 26s is one observation. More data needed.

---

## Claude Code

**Verified:** 2026-05-22 (v2.1.148) | **Recheck:** ~2026-08-01

Source: <https://code.claude.com/docs/en/mcp> and `anthropics/claude-code` CHANGELOG.md on `main`. Most agents reading this skill are running inside Claude Code — this section applies directly.

---

### Capabilities Declared by Claude Code

| Capability | Status | Details |
|------------|--------|---------|
| `elicitation` | ✅ since v2.1.76 | Server can request structured mid-task user input via an interactive dialog (form fields or browser URL). |
| `roots` | ⚠️ UNVERIFIED | Not confirmed in docs or CHANGELOG. |
| `sampling` | ❌ No evidence — ⚠️ Deprecated in DRAFT-2026-v1 (SEP-2596) | No mention in docs or CHANGELOG. Treat as unsupported. |
| `completions` | ⚠️ UNVERIFIED | Not confirmed. |
| OAuth 2.1 (remote servers) | ✅ since v1.0.27 | Full RFC 9728, CIMD (SEP-991 static client registration), `--client-id`/`--client-secret`, `oauth.authServerMetadataUrl` override, step-up auth, proactive token refresh, `headersHelper` dynamic-header script alternative. |

---

### Notifications

| Notification | Status | Details |
|---|---|---|
| `notifications/tools/list_changed` | ✅ since v2.1.0 | Servers can update tool/prompt/resource lists without reconnection. Declare `"tools": {"listChanged": true}` in capabilities. |
| `notifications/message` (logging) | ⚠️ UNVERIFIED | Not confirmed in docs. |
| `notifications/progress` | ⚠️ UNVERIFIED | Not confirmed in docs. |

---

### Resources and Prompts

- **Resources:** `@server:protocol://resource/path` mention syntax (e.g. `@github:issue://123`).
- **Prompts:** surfaced as slash commands `/mcp__<server>__<prompt>` (e.g. `/mcp__github__pr_review 456`).

---

### Timeouts and Output Limits

| Knob | Value | Notes |
|------|-------|-------|
| `MCP_TOOL_TIMEOUT` | no default published | Per-server tool-call timeout in **milliseconds**. Set as env var. |
| `MCP_TIMEOUT` | 5 000 ms | Server **startup** timeout (not tool-call). |
| `MAX_MCP_OUTPUT_TOKENS` | 25 000 (default) | Warning logged at 10 000. Per-tool override: `anthropic/maxResultSizeChars` ≤ 500 KB. |

---

### Tool Loading and Scopes

| Knob | Values | Effect |
|------|--------|--------|
| `ENABLE_TOOL_SEARCH` | `true` / `false` / `auto` | Deferred tool loading — tools fetched on demand. `alwaysLoad: true` on a server exempts it. |
| Server scope | `local` (`~/.claude.json`) · `project` (`.mcp.json`, git-shared) · `user` (`~/.claude.json`, all projects) | Controls who sees the server config. |

---

### Tool Name Constraints

No stricter-than-spec enforcement observed. CHANGELOG references tool-name issues but none relate to character-set rejection beyond MCP spec. The spec range (`^[A-Za-z0-9_\-.]{1,128}$`) is what Claude Code accepts; the snake_case convention pattern lives in [tool-design.md §Character set](tool-design.md).

---

### Dynamic Headers

`"headersHelper": "/path/to/script"` in `.mcp.json` — script is invoked per request. Env vars exposed to helper: `CLAUDE_CODE_MCP_SERVER_NAME`, `CLAUDE_CODE_MCP_SERVER_URL`. Use for token refresh or per-call signing without OAuth.

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

## Template: Adding a New Client

```markdown
## <Client Name>

**Verified:** YYYY-MM-DD | **Recheck:** YYYY-MM-DD

Source: <how findings were obtained>

### Capabilities Declared

| Capability | Status | Consequence |
|---|---|---|

### Notifications

| Notification | Status | Details |
|---|---|---|

### Timeouts

### Design Implications
```

**Status legend:**
- `❌ Not supported / dropped` — confirmed absent as of verified date
- `⚠️ UNVERIFIED` — needs targeted check before relying on it
- `✅ Works` — confirmed working as spec describes
