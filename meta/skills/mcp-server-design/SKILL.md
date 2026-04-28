---
name: mcp-server-design
description: >-
  Use when designing or auditing MCP (Model Context Protocol) servers — NOT for hands-on
  implementation (use mcp-builder for that). Covers design philosophy, tool naming,
  parameter schemas, agent UX, feedback channel,
  Covers design philosophy, tool naming, parameter schemas, agent UX, feedback channel,
  transport, security, and client compatibility. Should be used when the user asks to
  "design an MCP server", "audit an MCP server", "review MCP tools", "add MCP tool",
  "write MCP server", "improve tool descriptions", "design tool surface",
  "add SubmitFeedback tool", "write tool schema", mentions "MCP transport",
  "tool annotations", "mcp stdio", or is building, reviewing, or auditing any MCP server.
---

# Building MCP Servers

Patterns and conventions for production-grade MCP servers, distilled from multiple real deployments.

> **For hands-on implementation from scratch** (SDK setup, Python/TypeScript scaffolding,
> Pydantic/Zod schemas, evaluation harness) use the official Anthropic skill **`mcp-builder`**,
> available by default in most Claude Code installations:
> https://github.com/anthropics/skills/tree/main/skills/mcp-builder

## References

Load the relevant reference before proceeding:

- **Design philosophy** — [references/design-philosophy.md](references/design-philosophy.md)
  "Not an API wrapper" principles, antipatterns, Bad vs Good comparisons, 5 principles
- **Tool design** — [references/tool-design.md](references/tool-design.md)
  Naming, `title`, classification, annotations, descriptions, outputSchema, parameter schemas,
  error handling, pagination, long-running ops, argument flattening, listChanged
- **Agent UX** — [references/agent-ux.md](references/agent-ux.md)
  System prompt structure, dark-room testing, `Action:` error hints, post-MVP normalization
- **Feedback channel** — [references/feedback-tool.md](references/feedback-tool.md)
  `SubmitFeedback` tool interface, operator CLI contract, data model, status lifecycle
- **Security** — [references/security.md](references/security.md)
  Prompt injection, transport security, SSE deprecation clarification, annotation trust
- **Client compatibility** — [references/clients.md](references/clients.md)
  Claude Desktop capabilities, notification behavior, timeouts — empirically verified 2026-04-28
- **Audit checklist** — [references/audit-checklist.md](references/audit-checklist.md)
  15-section, ~80-item checklist for auditing existing servers; HIGH/MEDIUM/LOW findings

---

## Core Philosophy

- MCP servers are a **UI for agents**, not API wrappers
- Design tools around user goals — each tool completes an intent, not an endpoint
- Bundle orchestration (multiple API calls, data filtering, normalisation) inside the tool
- A good REST API is not a good MCP server — mapping endpoints 1:1 causes "tool pollution"
- **Tools are prompts.** Tool name and description are read by the LLM. Write for language models:
  explain *when* to call, *what triggers* the call, *what not to do*

→ Full philosophy, antipatterns, concrete Bad vs Good comparisons:
[references/design-philosophy.md](references/design-philosophy.md)

---

## Tool Design

Quick rules:

- Names: `PascalCase`, verb-noun — `ListDialogs`, `GetEntityInfo`, `SubmitFeedback`
- `title`: **mandatory** — 1–3 words, product language, sentence case, user-facing ("Search messages", not "SearchMessages")
- Classify each tool: `primary` (user-facing) or `secondary/helper` (plumbing)
- Annotate explicitly: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
- Declare `outputSchema` on structured tools — when declared, MUST return `structuredContent` on every call
- Use `isError: true` for business errors (validation, API failures) — never raise protocol exceptions for domain errors
- Error messages must be actionable: include what went wrong + `Action:` hint
- Flat parameter schemas — no nested objects; LLMs hallucinate nested key names
- Hard-cap all list responses; include pagination token when truncated
- Target ≤ 15 primary tools — past that, consolidate or split into domain servers

→ Full conventions: [references/tool-design.md](references/tool-design.md)

---

## Agent Feedback Channel

Every MCP server should expose a `SubmitFeedback` tool:

- Write-only for the agent — no read-back, no tracking ID, fire and forget
- Agent reports bugs, confusing behaviour, missing capabilities in the moment
- Operator reviews out-of-band via `feedback list` / `feedback status` / `feedback delete`
- Separate storage from the server's main data (own SQLite file or table)
- System prompt must include the directive: *"Use SubmitFeedback immediately when a tool
  response is wrong, surprising, or missing a useful capability."*

→ Full interface spec (fields, severity, CLI contract, data model):
[references/feedback-tool.md](references/feedback-tool.md)

---

## Agent UX

- Tool descriptions serve two audiences: LLM (reads as prompt) and human (sees in UI). Write for LLM first
- System prompt (`server.instructions`): ≤ 300 tokens, ALL-CAPS named workflow patterns, built dynamically at startup
- Dark-room UX test: agent + server + real task + no briefing → review feedback queue
- Error messages: include `Action:` hint for every recoverable error — agents act on error text directly

→ Full patterns: [references/agent-ux.md](references/agent-ux.md)

---

## Daemon + On-Demand Server Architecture

When the server needs a long-running backend resource, split into two processes:

- **Daemon** — container PID 1; owns the backend resource exclusively; exposes Unix socket
- **MCP server** — started on demand; stateless; connects to daemon; exits when client disconnects

```
Claude Desktop
    │ stdio (docker exec -i)
    ▼
MCP server process  ──(Unix socket, newline-JSON)──▶  Daemon process
    (ephemeral)                                        (PID 1, persistent)
```

Operational rules:

- Delete stale socket file at daemon startup before `bind()` — crash leaves socket on disk
- MCP server must keep reading stdin until client closes — premature exit silently kills the session
- Daemon-not-running errors must produce a single user-facing actionable message, not a raw socket exception
- Crash isolation: MCP server crash → daemon unaffected; daemon crash → MCP server returns clean error per call

---

## Transport

- **The old HTTP+SSE transport (spec 2024-11-05) is deprecated — never use it**
- `stdio`: use for Claude Desktop and any client that launches subprocesses
- Streamable HTTP: use for inter-container (Docker network) or HTTP-capable clients
- **All logging MUST go to `stderr`** — any `stdout` output corrupts the JSON-RPC transport silently

→ Security per transport: [references/security.md](references/security.md)
→ Client limitations (Claude Desktop, Cursor): [references/clients.md](references/clients.md)

---

## Security

- **Prompt injection** — delimit untrusted content in tool responses; never inject raw message/file/DB content
- **Localhost exposure** — bind to `127.0.0.1` or Unix socket; never expose without auth on public interface
- **Annotation trust** — annotations are hints only; enforcement belongs in server access control, not client

→ Full details: [references/security.md](references/security.md)

---

## Testing and Validation

- Unit tests: cover tool logic and schema validation in isolation
- Integration smoke test: call every tool through the actual transport against a live server
- After any code change: rebuild (if containerised) and run smoke test before marking done
- Green unit tests do not prove the live server works — green smoke test does

---

## Auditing an Existing Server

→ [references/audit-checklist.md](references/audit-checklist.md) — 15-section, ~80-item checklist,
`*` marks high-priority items, produces HIGH / MEDIUM / LOW findings summary.

---

## Quick Checks

Before shipping or handing off:

- [ ] `title` set on every tool — 1–3 words, product language, sentence case, user-facing
- [ ] Tools designed for outcomes (user goals), not 1:1 endpoint wrappers
- [ ] Tool count ≤ 15 primary tools
- [ ] `SubmitFeedback` present — write-only, fire-and-forget, no read-back
- [ ] System prompt includes feedback directive, ≤ 300 tokens, built dynamically
- [ ] `outputSchema` declared tools always return `structuredContent` (MUST, not optional)
- [ ] All business errors use `isError: true` — no protocol exceptions for domain errors
- [ ] All logging to `stderr`, never `stdout`
- [ ] Integration smoke test exists and passes against live server
- [ ] No nested objects in parameter schemas — flat primitives only

---

## External References

- [MCP Specification (2025-11-25, stable)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Specification (draft)](https://modelcontextprotocol.io/specification/draft)
- [MCP Docs](https://modelcontextprotocol.io/docs)
