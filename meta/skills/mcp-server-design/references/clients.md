# MCP Client Compatibility Notes

> **Load when:** Designing tools or server behaviour that may be affected by client limitations.
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
| `sampling` | ❌ NOT declared | Server cannot call `sampling/createMessage` |
| `elicitation` | ❌ NOT declared | Server cannot prompt the user mid-execution |
| `roots` | ❌ NOT declared | Server cannot request workspace root directories |
| `completions` | ❌ NOT declared | Parameter autocompletion not supported |
| `io.modelcontextprotocol/ui` | ✅ declared | Proprietary — likely HTML/React artefact rendering in UI. Does not affect tool UX. |

**Bottom line:** Claude Desktop supports only the basic MCP surface (tools). No interactive server-to-client capabilities.

---

### Server → Client Notifications

| Notification | Status | Details |
|---|---|---|
| `notifications/message` (logging) | ❌ Silently dropped | Transport delivers it; model never sees it. Agent confirmed it receives no log messages or progress. Do not use for progress reporting. |
| `notifications/progress` | ❌ Not functional | Requires `progressToken` in `_meta` — Claude Desktop (stdio) does not send it. Verified 2026-04-28. |
| `notifications/tools/list_changed` | ⚠️ UNVERIFIED | Likely dropped — no matching capability declared. |
| `notifications/resources/updated` | ⚠️ UNVERIFIED | Same assumption — likely dropped. |

**Practical rule:** do not rely on any server-push notification reaching the model. All communication to the model must go through tool responses, `isError` errors, tool descriptions, or `server.instructions`.

---

### Timeouts

- **Socket closes after ~26 seconds** if a tool call has not returned (observed with an LLM-enriched search operation).
- **After socket close:** server continues executing (lock held), but the result has nowhere to go.
- **On reconnect:** a new call finds the lock and receives the "server busy" message — **agent sees this and can act on it**.
- **Design target:** tool calls should complete in <20 seconds for stable operation. 26s is a single empirical observation, not a hard spec limit.

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
| `sampling/createMessage` | ❌ Not supported | — |

---

### Design Implications for Claude Desktop

**Tool call duration:**
- Target <20s. Anything longer risks connection drop.
- For slow operations: return a partial result immediately; agent can poll via a follow-up call.
- "Server busy" with remaining time estimate is visible to the agent — write informative busy messages.

**Tool names:**
- Watch for namespace collisions with client meta-operations. `GetMe` was intercepted by Claude Desktop as a client-side operation → renamed `GetMyAccount`.

**All context must be in descriptions and system prompt:**
- Notifications don't work → schema, behaviour, limits, failure modes all belong in tool descriptions and `server.instructions`.
- Describe failure modes explicitly: "if session expired — do X", "if server busy — retry in N seconds".
- Describe tool dependencies: "call SearchX before QueryX".

**What NOT to implement for Claude Desktop:**
- Push progress notifications (model won't see them)
- `elicitation` mid-execution (not supported)
- `sampling/createMessage` (not supported)
- Resource subscriptions (likely dropped, unverified)

---

### Open Questions (to verify)

- **`io.modelcontextprotocol/ui`:** what exactly can the server return to trigger HTML rendering? Tool response with specific MIME type?
- **Timeout precision:** 26s is one observation. More data needed.

---

## Cursor

**Verified:** — | **Recheck:** —

*(No data yet)*

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
