---
name: mcp-server-design
description: >-
  This skill should be used when the user asks to "design an MCP server", "audit an MCP server",
  "review MCP tools", "add MCP tool", "write MCP server", "improve tool descriptions",
  "design tool surface", "add submit_feedback tool", "write tool schema", mentions "MCP transport",
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
- **OPINIONATED** — recommended default distilled from one or a handful of real production
  servers, not from controlled studies. Treat as a strong starting point worth measuring on
  your own surface; adapt or skip when it does not match the project. Items that cite a
  specific study or n-of-servers do so inline.
- **STACK-SPECIFIC** — applies only to the named stack, framework, client, or deployment shape; inline as `[STACK:label]` where `label` names the specific stack (e.g. `[STACK:Python]`, `[STACK:stateful-backends]`)
- **EMPIRICAL** — observed client behaviour; verify when the client version or date matters
- **CONDITIONAL** — applies when the named precondition holds (specific transport, deployment
  shape, or stack); skip otherwise

When in doubt, enforce UNIVERSAL rules first. Do not treat OPINIONATED or STACK-SPECIFIC recipes
as protocol requirements.

## Glossary

One-liners for the MCP-specific terms used throughout this skill. Full mechanics live in
the references they link to.

| Term | One-line meaning |
|------|------------------|
| `stdio` transport | MCP over a process's stdin/stdout; the host launches the server as a subprocess. Default for Claude Desktop and CLI hosts. |
| `Streamable HTTP` transport | The current MCP network transport (spec 2025-11-25): standard HTTP with an SSE upgrade and a session header. Replaces deprecated HTTP+SSE. |
| `outputSchema` | JSON Schema declared on a tool that types its structured output. When declared, the server MUST return `structuredContent` on every successful call. |
| `structuredContent` | Sibling of `content` in a tool result — carries typed JSON conforming to `outputSchema`. Lets clients render/parse without re-parsing text. |
| `isError` | Boolean on the tool result. `true` = business/validation error the agent can recover from. Distinct from protocol exceptions (transport-level failures). |
| `execution.taskSupport` | Per-tool field (`DRAFT-2025-11-25`, SEP-1686): `forbidden` \| `optional` \| `required`. Declares whether the client may (or must) augment a `tools/call` with a `task` param to run it as a polled task via `tasks/get` / `tasks/result`. Spec primitive for long-running ops. |
| `server.instructions` | The server-declared system prompt — first-class config surface for shaping agent behaviour without adding tools. Paid per request; keep tight. |
| Tool `annotations` | Protocol hints on a tool: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title`. Hints to clients/agents, not enforced server-side. |
| `posture` (primary / secondary) | Project-level classification: *primary* tools = user-facing capabilities; *secondary/helper* tools = plumbing the agent uses to support primary calls. Not a protocol field. |

---

## References

Load references by use case:

| Use case | Read |
|----------|------|
| **Auditing** an existing server | audit-checklist plus the UNIVERSAL refs; add conditional refs only when the stack matches |
| **Designing** a new server | design-philosophy, tool-design, agent-ux, feedback-tool, security-threats, observability, clients; then choose opinionated modules deliberately |
| **Security review** | security-threats, clients, audit-checklist (§14 Security, §12 Transport and Logging, §5 Parameter Schemas) |
| **Tool-surface review / 80-20 audit** | observability, audit-checklist (§1 Design Philosophy) |
| **Stateful backend** (DB, WebSocket, ML model) | daemon-architecture |
| **Python/Pydantic implementation** | python-notes, tool-design |
| **FastMCP framework** | python-notes, fastmcp-notes, tool-design |
| **Remote multi-server gateway** | gateway-aggregation, security-threats, clients, audit-checklist |

- **Design philosophy** *(UNIVERSAL)* — [references/design-philosophy.md](references/design-philosophy.md)
  "Not an API wrapper" principles, antipatterns, Bad vs Good comparisons, 5 principles
- **Tool design** *(UNIVERSAL, with opinionated thresholds)* — [references/tool-design.md](references/tool-design.md)
  Naming, `title`, classification, annotations, descriptions, outputSchema, parameter schemas,
  safe defaults, error diagnostics, compact responses, pagination, long-running ops,
  argument flattening, listChanged
- **Agent UX** *(UNIVERSAL + OPINIONATED)* — [references/agent-ux.md](references/agent-ux.md)
  System prompt structure, dark-room testing, `Action:` error hints, post-MVP normalization
- **Feedback channel** *(OPINIONATED)* — [references/feedback-tool.md](references/feedback-tool.md)
  `submit_feedback` tool interface, operator CLI contract, data model, status lifecycle
- **Security** *(UNIVERSAL)* — [references/security-threats.md](references/security-threats.md)
  Prompt injection, transport security, annotation trust; threat model for benign servers:
  data injection, arg validation, authn/authz, sessions, resource exhaustion, secret
  hygiene, supply chain, release stability
- **Observability** *(UNIVERSAL + OPINIONATED)* — [references/observability.md](references/observability.md)
  Tool-usage logging; schema, storage patterns (JSONL / DB table / structured log),
  privacy rules, reports for dead-tool / hot-tool / error-rate decisions
- **Client compatibility** *(EMPIRICAL)* — [references/clients.md](references/clients.md)
  Claude Desktop capabilities, notification behavior, timeouts — empirically verified 2026-04-28
- **Audit checklist** *(MIXED; items are tagged)* — [references/audit-checklist.md](references/audit-checklist.md)
  16-section checklist for auditing existing servers; apply item tags before severity
- **Daemon architecture** `[STACK:stateful-backends]` — [references/daemon-architecture.md](references/daemon-architecture.md)
  Daemon + on-demand split, Unix socket, crash isolation, when NOT to use
- **Gateway aggregation** `[STACK:remote-multi-server]` — [references/gateway-aggregation.md](references/gateway-aggregation.md)
  Docker MCP Gateway / registry pattern, shared OAuth edge, public tunnel, private backends,
  tool-surface curation, smoke tests, failure modes
- **Python notes** `[STACK:Python]` — [references/python-notes.md](references/python-notes.md)
  Pydantic v2 `anyOf: null` recipes, `Annotated`/`Field` schema docs,
  MCP Python SDK gotchas, return-type pitfalls, stdout/stderr logging
- **FastMCP specifics** `[STACK:FastMCP]` — [references/fastmcp-notes.md](references/fastmcp-notes.md)
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
- `title`: **mandatory** — 1–3 words, product language, sentence case, user-facing ("Search messages", not the raw tool name `search_messages`)
- Classify each tool: `primary` (user-facing) or `secondary/helper` (plumbing)
- Annotate explicitly: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
- Mutating tools default to safe states: drafts, paused resources, dry-run, conservative limits
- Declare `outputSchema` on structured tools — when declared, MUST return `structuredContent` (`structuredContent` is a sibling key to `content` in an MCP tool result that carries typed JSON data conforming to the declared `outputSchema`; see tool-design.md) on every call
- Use `isError: true` for business errors (validation, API failures) — never raise protocol exceptions for domain errors
- Error messages must be actionable: include what went wrong + diagnostic detail + `Action:` hint
- Flat parameter schemas — no nested objects; LLMs hallucinate nested key names
- Hard-cap all list responses; include pagination token when truncated
- ≤10 primary tools is a signal, not a hard cap *(OPINIONATED — rationale and exceptions in `references/tool-design.md` §Classification)*

→ Full conventions: [references/tool-design.md](references/tool-design.md)

---

## Agent Feedback Channel *(OPINIONATED · CONDITIONAL)*

A useful pattern for **self-owned production servers with a maintainer who reads the queue** —
not an MCP protocol requirement. Skip this entirely for adversarial environments, deployments
without an active reviewer, or short-lived/demo servers — see
[feedback-tool.md §When NOT to use](references/feedback-tool.md#when-not-to-use).

If you adopt the pattern:

- Write-only for the agent — no read-back, no tracking ID, fire and forget
- Agent reports bugs, confusing behaviour, missing capabilities in the moment
- Operator reviews out-of-band via `feedback list` / `feedback status` / `feedback delete`
- Separate storage from the server's main data (own SQLite file or table)
- Pair with a system-prompt directive: *"Use `submit_feedback` immediately when a tool
  response is wrong, surprising, or missing a useful capability."*

→ Full interface spec (fields, severity, CLI contract, data model, when-not-to-use):
[references/feedback-tool.md](references/feedback-tool.md)

---

## Agent UX

- Tool descriptions serve two audiences: LLM (reads as prompt) and human (sees in UI). Write for LLM first
- System prompt (`server.instructions`): keep minimal — grow only when you see agents making wrong decisions without the directive. ALL-CAPS named workflow patterns, built dynamically at startup
- Dark-room UX test: agent + server + real task + no briefing → review feedback queue
- Error messages: include `Action:` hint for every recoverable error — agents act on error text directly

→ Full patterns: [references/agent-ux.md](references/agent-ux.md)

---

## Daemon + On-Demand Architecture `[STACK:stateful-backends]`

Skip this section unless your backend is stateful or requires shared infrastructure across tool calls.

→ [references/daemon-architecture.md](references/daemon-architecture.md) — daemon/MCP split,
Unix socket rules, crash isolation, when NOT to use this pattern.

---

## Transport

**Decision tree** (apply in order — first matching branch wins, then keep walking for the auth layer):

- Server launched as a subprocess by Claude Desktop / a CLI host? → **`stdio`**
- Network-accessible (inter-container Docker, HTTP-capable clients)? → **Streamable HTTP**
- Exposed outside a trusted network? → **add an auth layer** on top (OAuth 2.1 per the spec; internal Docker networks with no untrusted neighbours can stay plaintext)

> **Streamable HTTP** is the current MCP network transport (spec 2025-11-25), replacing the deprecated HTTP+SSE transport — it uses standard HTTP with an SSE upgrade path and a session header.

- **The old HTTP+SSE transport (spec 2024-11-05) is deprecated — never use it**
- `stdio`: use for Claude Desktop and any client that launches subprocesses
- Streamable HTTP: use for inter-container (Docker network) or HTTP-capable clients
- `[STACK:remote-multi-server]` Put auth/proxy/ingress in front of a curated gateway, not in every backend server
- For `stdio`, **all logging goes to `stderr`** — `stdout` carries JSON-RPC and any other byte corrupts the transport silently. `[CONDITIONAL]` Exception: under the daemon + on-demand server pattern, stderr is piped to the MCP client (not the operator), so the MCP server must NOT write to stderr — it ships logs to the daemon over the socket. Canonical rule and rationale: [references/daemon-architecture.md](references/daemon-architecture.md)

→ Gateway aggregation: [references/gateway-aggregation.md](references/gateway-aggregation.md)
→ Security per transport: [references/security-threats.md](references/security-threats.md)
→ Client limitations (Claude Desktop, Cursor): [references/clients.md](references/clients.md)

---

## Security

- **Prompt injection** — delimit untrusted content in tool responses; never inject raw message/file/DB content
- **Localhost exposure** — bind to `127.0.0.1` or Unix socket; never expose without auth on public interface
- **Annotation trust** — annotations are hints only; enforcement belongs in server access control, not client
- **Input boundary** — validate all paths, shell arguments, URLs, tenant IDs, and secrets server-side

→ Threat reference (data injection, authn/authz, sessions, DoS, secrets, supply chain, release stability):
   [references/security-threats.md](references/security-threats.md)

---

## Observability *(UNIVERSAL + OPINIONATED)*

Per-call usage logs drive three decisions no intuition can replace: which tools are dead
(rewrite or delete), which are hot (invest description work there first), which are
error-prone (agent-UX bug, not a backend bug). Minimum fields per call: `ts`,
`tool_name`, `status`, `duration_ms`. Never log raw args or responses — secrets, PII,
prompt-injected content. See [references/observability.md](references/observability.md)
for schema, storage patterns, privacy rules, and report templates.

---

## Testing and Validation

- Unit tests: cover tool logic and schema validation in isolation
- Integration smoke test: call every tool through the actual transport against a live server
- After any code change: rebuild (if containerised) and run smoke test before marking done
- Green unit tests do not prove the live server works — green smoke test does

---

## Auditing an Existing Server

→ [references/audit-checklist.md](references/audit-checklist.md) — 16-section, ~80-item checklist,
`*` marks high-priority items, produces HIGH / MEDIUM / LOW findings summary.

---

## Quick Checks

Before shipping or handing off:

- [ ] `title` set on every tool — 1–3 words, product language, sentence case, user-facing
- [ ] Tools designed for outcomes (user goals), not 1:1 endpoint wrappers
- [ ] Primary tool count scrutinised against the ≤10 signal *(OPINIONATED — see `references/tool-design.md` §Classification)*
- [ ] Mutating tools are safe by default — draft/paused/dry-run unless explicit activation requested
- [ ] *(if adopting feedback pattern — see `references/feedback-tool.md` §When NOT to use)* `submit_feedback` present *(OPINIONATED)* — write-only, fire-and-forget, no read-back
- [ ] *(if adopting feedback pattern)* System prompt includes feedback directive *(OPINIONATED)*, kept short, built dynamically
- [ ] `outputSchema` declared tools always return `structuredContent` (MUST, not optional)
- [ ] Business errors use `isError: true` with actionable diagnostics — no protocol exceptions
- [ ] For `stdio`, logs go to `stderr`, never `stdout`
- [ ] Integration smoke test exists and passes against live server
- [ ] No nested objects in parameter schemas — flat primitives only
- [ ] Per-call usage log in place — `ts`, `tool_name`, `status`, `duration_ms` minimum; no raw args / no responses logged *(OPINIONATED)*

---

## External References

- [MCP Specification (2025-11-25, stable)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Specification (draft)](https://modelcontextprotocol.io/specification/draft)
- [MCP Docs](https://modelcontextprotocol.io/docs)
