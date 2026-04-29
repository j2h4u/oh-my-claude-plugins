# Daemon + On-Demand Server Architecture

Use this pattern when the MCP server needs a long-running backend resource (database connection,
persistent WebSocket, ML model loaded in memory, etc.) that cannot be cheaply recreated per request.

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
  Do NOT write logs to `stderr` from the MCP server — stderr goes to the MCP client, not the operator.

## When NOT to Use This Pattern

- Server is stateless by nature (REST proxy, file operations, read-only queries) → skip the daemon
- Single-request startup cost is acceptable → skip the daemon
- Running outside Docker / no PID 1 concern → simpler process management may suffice
