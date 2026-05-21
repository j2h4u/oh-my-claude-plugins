---
name: mcp-server-design
description: >-
  This skill should be used when the user asks to "design an MCP server", "audit an MCP server",
  "review MCP tools", "add MCP tool", "write MCP server", "improve tool descriptions",
  "design tool surface", "add SubmitFeedback tool", "write tool schema", mentions "MCP transport",
  "tool annotations", "mcp stdio", or is building, reviewing, or auditing any MCP server.
  Covers design philosophy, tool naming, parameter schemas, agent UX, feedback channel,
  transport, security, and client compatibility. NOT for hands-on implementation from scratch
  (use mcp-builder for that).
---

# Building MCP Servers

Patterns and conventions for production-grade MCP servers, distilled from multiple real deployments.

> **For hands-on implementation from scratch** (SDK setup, Python/TypeScript scaffolding,
> Pydantic/Zod schemas, evaluation harness) use the official Anthropic skill **`mcp-builder`**,
> available by default in most Claude Code installations:
> https://github.com/anthropics/skills/tree/main/skills/mcp-builder

## Scope Tags

This skill intentionally mixes universal MCP guidance with narrower production recipes. Treat
the tags below as binding when applying the references:

- **UNIVERSAL** — applies to any MCP server, independent of language, SDK, transport, or host
- **OPINIONATED** — recommended default from production practice; adapt or skip when it does not
  match the project
- **STACK-SPECIFIC** — applies only to the named stack, framework, client, or deployment shape
- **EMPIRICAL** — observed client behaviour; verify when the client version or date matters

When in doubt, enforce UNIVERSAL rules first. Do not treat OPINIONATED or STACK-SPECIFIC recipes
as protocol requirements.

## References

Load references by use case:

| Use case | Read |
|----------|------|
| **Auditing** an existing server | audit-checklist plus the UNIVERSAL refs; add conditional refs only when the stack matches |
| **Designing** a new server | design-philosophy, tool-design, security; then choose opinionated modules deliberately |
| **Security review** | security, clients, audit-checklist (sections 1, 4, 8) |
| **Stateful backend** (DB, WebSocket, ML model) | daemon-architecture |
| **Python/Pydantic implementation** | python-notes, tool-design |
| **FastMCP framework** | python-notes, fastmcp-notes, tool-design |
| **Remote multi-server gateway** | gateway-aggregation, security, clients, audit-checklist |

- **Design philosophy** *(UNIVERSAL)* — [references/design-philosophy.md](references/design-philosophy.md)
  "Not an API wrapper" principles, antipatterns, Bad vs Good comparisons, 5 principles
- **Tool design** *(UNIVERSAL, with opinionated thresholds)* — [references/tool-design.md](references/tool-design.md)
  Naming, `title`, classification, annotations, descriptions, outputSchema, parameter schemas,
  safe defaults, error diagnostics, compact responses, pagination, long-running ops,
  argument flattening, listChanged
- **Agent UX** *(UNIVERSAL + OPINIONATED)* — [references/agent-ux.md](references/agent-ux.md)
  System prompt structure, dark-room testing, `Action:` error hints, post-MVP normalization
- **Feedback channel** *(OPINIONATED)* — [references/feedback-tool.md](references/feedback-tool.md)
  `SubmitFeedback` tool interface, operator CLI contract, data model, status lifecycle
- **Security** *(UNIVERSAL)* — [references/security.md](references/security.md)
  Prompt injection, transport security, SSE deprecation clarification, annotation trust
- **Client compatibility** *(EMPIRICAL)* — [references/clients.md](references/clients.md)
  Claude Desktop capabilities, notification behavior, timeouts — empirically verified 2026-04-28
- **Audit checklist** *(MIXED; items are tagged)* — [references/audit-checklist.md](references/audit-checklist.md)
  15-section checklist for auditing existing servers; apply item tags before severity
- **Daemon architecture** *(STACK-SPECIFIC: stateful backends only)* — [references/daemon-architecture.md](references/daemon-architecture.md)
  Daemon + on-demand split, Unix socket, crash isolation, when NOT to use
- **Gateway aggregation** *(STACK-SPECIFIC: remote multi-server deployments)* — [references/gateway-aggregation.md](references/gateway-aggregation.md)
  Docker MCP Gateway / registry pattern, shared OAuth edge, public tunnel, private backends,
  tool-surface curation, smoke tests, failure modes
- **Python notes** *(STACK-SPECIFIC: Python ecosystem)* — [references/python-notes.md](references/python-notes.md)
  Pydantic v2 `anyOf: null` recipes, `Annotated`/`Field` schema docs,
  MCP Python SDK gotchas, return-type pitfalls, stdout/stderr logging
- **FastMCP specifics** *(STACK-SPECIFIC: FastMCP framework only)* — [references/fastmcp-notes.md](references/fastmcp-notes.md)
  What FastMCP handles automatically, tool name override via `name=`, framework-only bugs

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

- Names: `snake_case`, verb_noun — `list_dialogs`, `get_entity_info`, `submit_feedback`
- `title`: **mandatory** — 1–3 words, product language, sentence case, user-facing ("Search messages", not "SearchMessages")
- Classify each tool: `primary` (user-facing) or `secondary/helper` (plumbing)
- Annotate explicitly: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
- Mutating tools default to safe states: drafts, paused resources, dry-run, conservative limits
- Declare `outputSchema` on structured tools — when declared, MUST return `structuredContent` on every call
- Use `isError: true` for business errors (validation, API failures) — never raise protocol exceptions for domain errors
- Error messages must be actionable: include what went wrong + diagnostic detail + `Action:` hint
- Flat parameter schemas — no nested objects; LLMs hallucinate nested key names
- Hard-cap all list responses; include pagination token when truncated
- Target ≤ 15 primary tools *(OPINIONATED threshold)* — past that, consolidate or split into domain servers

→ Full conventions: [references/tool-design.md](references/tool-design.md)

---

## Agent Feedback Channel *(OPINIONATED)*

For self-owned production servers, this skill recommends exposing a `SubmitFeedback` tool. This
is a strong default, not an MCP protocol requirement:

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

## Daemon + On-Demand Architecture *(stateful backends only)*

→ [references/daemon-architecture.md](references/daemon-architecture.md) — daemon/MCP split,
Unix socket rules, crash isolation, when NOT to use this pattern.

---

## Transport

- **The old HTTP+SSE transport (spec 2024-11-05) is deprecated — never use it**
- `stdio`: use for Claude Desktop and any client that launches subprocesses
- Streamable HTTP: use for inter-container (Docker network) or HTTP-capable clients
- Remote multi-server deployments *(STACK-SPECIFIC)*: put auth/proxy/ingress in front of a curated gateway, not
  in every backend server
- For `stdio`, **all logging MUST go to `stderr`** — any `stdout` output corrupts the JSON-RPC transport silently

→ Gateway aggregation: [references/gateway-aggregation.md](references/gateway-aggregation.md)
→ Security per transport: [references/security.md](references/security.md)
→ Client limitations (Claude Desktop, Cursor): [references/clients.md](references/clients.md)

---

## Security

- **Prompt injection** — delimit untrusted content in tool responses; never inject raw message/file/DB content
- **Localhost exposure** — bind to `127.0.0.1` or Unix socket; never expose without auth on public interface
- **Annotation trust** — annotations are hints only; enforcement belongs in server access control, not client
- **Input boundary** — validate all paths, shell arguments, URLs, tenant IDs, and secrets server-side

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
- [ ] Tool count ≤ 15 primary tools *(OPINIONATED threshold)*
- [ ] Mutating tools are safe by default — draft/paused/dry-run unless explicit activation requested
- [ ] `SubmitFeedback` present *(OPINIONATED)* — write-only, fire-and-forget, no read-back
- [ ] System prompt includes feedback directive *(OPINIONATED)*, ≤ 300 tokens, built dynamically
- [ ] `outputSchema` declared tools always return `structuredContent` (MUST, not optional)
- [ ] Business errors use `isError: true` with actionable diagnostics — no protocol exceptions
- [ ] For `stdio`, logs go to `stderr`, never `stdout`
- [ ] Integration smoke test exists and passes against live server
- [ ] No nested objects in parameter schemas — flat primitives only

---

## External References

- [MCP Specification (2025-11-25, stable)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Specification (draft)](https://modelcontextprotocol.io/specification/draft)
- [MCP Docs](https://modelcontextprotocol.io/docs)
