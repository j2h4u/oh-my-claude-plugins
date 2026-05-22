# Daemon + On-Demand Server Architecture

> **Scope:** STACK-SPECIFIC / CONDITIONAL. Use only when a server has expensive persistent
> state or a long-running backend resource; skip for ordinary stateless MCP servers.

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

## Stderr Rule — Reversed Under This Pattern

This is the canonical source for the stderr-inversion rule (SKILL.md, security-threats.md, and
python-notes.md link here):

- **Standard stdio rule:** log to `stderr`, never `stdout` — stdout carries JSON-RPC and any other
  byte corrupts the transport.
- **Under the daemon pattern:** the MCP server is launched by the client (`docker exec -i`),
  so its `stderr` is piped to the **MCP client**, not the operator. Writing logs there leaks them
  into the client's diagnostic stream and the operator never sees them. The MCP server must NOT
  write to stderr; it ships logs to the daemon over the Unix socket, and the daemon writes the sink.
- Net effect for this pattern: stdin = JSON-RPC in, stdout = JSON-RPC out, stderr = silent,
  socket = logs + RPC to daemon.

## When NOT to Use This Pattern

- Server is stateless by nature (REST proxy, file operations, read-only queries) → skip the daemon
- Single-request startup cost is acceptable → skip the daemon
- Running outside Docker / no PID 1 concern → simpler process management may suffice
