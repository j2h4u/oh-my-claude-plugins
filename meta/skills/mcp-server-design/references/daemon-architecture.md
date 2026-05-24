# Daemon + On-Demand Server Architecture

> `[STACK-SPECIFIC / CONDITIONAL]` Use only when the server holds a long-running backend resource (DB connection, persistent WebSocket, in-memory ML model) that cannot be cheaply recreated per request. Skip for stateless MCP servers.

Split into two processes:

- **Daemon** — container PID 1; owns the backend resource exclusively; exposes Unix socket
- **MCP server** — started on demand by the MCP client; stateless; connects to daemon via socket;
  exits when client disconnects

```
Claude Desktop
    │ stdio (docker exec -i)
    ▼
MCP server process  ──(Unix socket, newline-JSON)──▶  Daemon process
    (ephemeral)                                        (PID 1, persistent)
```

## Operational Rules

- **Stale socket** — delete socket file at daemon startup before `bind()`; a crash leaves it on disk
- **Stdin lifecycle** — MCP server must keep reading stdin until client closes; premature exit
  silently kills the session
- **Daemon-not-running error** — must produce a single user-facing actionable message, not a raw
  socket exception (e.g. `"Server not running. Start with: docker compose up -d"`)
- **Crash isolation** — MCP server crash → daemon unaffected; daemon crash → MCP server returns
  a clean error per call (does not crash itself)
- **Logging via socket** — MCP server sends all log entries to the daemon over the same Unix socket
  (as a structured log message type alongside RPC calls); daemon owns the log sink (file, journal).

## Stderr Rule — Reversed Under This Pattern

Canonical source (SKILL.md, security-threats.md, observability.md link here).

| Pattern | `stdin` | `stdout` | `stderr` | Logs go to |
|---|---|---|---|---|
| Standard stdio | JSON-RPC in | JSON-RPC out | logs | stderr |
| Daemon + on-demand | JSON-RPC in | JSON-RPC out | **silent** | daemon (via Unix socket) |

Why the inversion: the daemon-pattern MCP server is launched by the client (`docker exec -i`), so its `stderr` pipes into the **client's** diagnostic stream — the operator never sees it. Logs must travel to the daemon over the socket; the daemon writes the sink.

## When NOT to Use This Pattern

- Server is stateless by nature (REST proxy, file operations, read-only queries) → skip the daemon
- Single-request startup cost is acceptable → skip the daemon
- Running outside Docker / no PID 1 concern → simpler process management may suffice
