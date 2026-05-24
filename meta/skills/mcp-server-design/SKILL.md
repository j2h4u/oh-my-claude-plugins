---
name: mcp-server-design
description: >-
  This skill should be used when the user asks to "design an MCP server", "audit an MCP server",
  "review MCP tools", "add MCP tool", "improve tool descriptions", "design tool surface",
  "add submit_feedback tool", "review tool schema", mentions "MCP transport", "tool annotations",
  "mcp stdio", "MCP Resources", "MCP Prompts", or is designing, reviewing, or auditing any MCP server.
  Covers design philosophy, tool naming, parameter schemas, agent UX, feedback channel,
  transport, security, and client compatibility. NOT for hands-on implementation from scratch
  (use mcp-builder for that).
---

# Building MCP Servers

This skill: tool/schema design, agent UX, security threat model, audit checklists, client compatibility — *what and why*. Pair with **`mcp-builder`** ([anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/mcp-builder)) for *how to wire it up* — SDK setup, scaffolding, deployment, language idioms.

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
| `Streamable HTTP` transport | The current MCP network transport (spec 2025-11-25): single endpoint, POST + GET. Server returns `application/json` or `text/event-stream` per response. Client MUST send `MCP-Protocol-Version` header. Replaces deprecated HTTP+SSE. |
| **Resource** | Read-only addressable content the client/application selects and injects. Stable, URI-addressable. In Claude Code: `@server:proto://path` mention syntax (e.g. `@github:issue://123`). → [tool-design.md §Three Primitives](references/tool-design.md#three-primitives) |
| **Prompt** | Parameterized text snippet the user invokes by name. Surfaces in Claude Code as `/mcp__<server>__<prompt>` slash command. → [tool-design.md §Three Primitives](references/tool-design.md#three-primitives) |
| `outputSchema` | JSON Schema declared on a tool that types its structured output. When declared, the server MUST return `structuredContent` on every successful call. |
| `structuredContent` | Sibling of `content` in a tool result — carries typed JSON conforming to `outputSchema`. Lets clients render/parse without re-parsing text. |
| `isError` | Boolean on the tool result. `true` = business/validation error the agent can recover from. Distinct from protocol exceptions (transport-level failures). |
| `execution.taskSupport` | Per-tool field (spec **2025-11-25**, experimental, SEP-1686): `forbidden` (default) \| `optional` \| `required`. Declares whether the client may (or must) augment a `tools/call` with a `task` param to run it as a polled task via `tasks/get` / `tasks/result`. Spec primitive for long-running ops. SDK + client support is rolling out — check [clients.md](references/clients.md) before marking `required`. |
| Tasks two-layer handshake | Tasks (SEP-1686) requires **both** sides to opt in: the server declares the `tasks` capability at `initialize` (`{"tasks": {"requests": {"tools/call": true}}}`), AND the client must declare matching capability. Per-tool `execution.taskSupport` only fires when both sides negotiated `tasks`. As of 2026-05, no tracked client negotiates `tasks` — see [clients.md cross-client matrix](references/clients.md#cross-client-capability-matrix). Roll-your-own async handle is the working default today. Full wire-shape: [tool-design.md §Long-Running Operations](references/tool-design.md#long-running-operations). |
| `server.instructions` | The server-declared system prompt — first-class config surface for shaping agent behaviour without adding tools. Sent at `initialize` (once per session); the host then folds it into its system prompt for the conversation. Keep it tight. |
| Tool `annotations` | Protocol hints on a tool: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title`. Hints to clients/agents, not enforced server-side. **Asymmetric default:** `destructiveHint` defaults to `true` (opt-out — you set `false` to declare additive/safe). The other three default to the *pessimistic* value (`readOnly:false`, `idempotent:false`, `openWorld:true`) and you opt *in* to the safer property. Forgetting to set `destructiveHint: false` on additive writes (e.g. `submit_feedback`) silently marks them destructive. → [tool-design.md §Annotations](references/tool-design.md#annotations). |
| `posture` (primary / secondary) | Project-level classification: *primary* tools = user-facing capabilities; *secondary/helper* tools = plumbing the agent uses to support primary calls. Not a protocol field. |
| `resource_link` | Tool result content type (`{type:"resource_link", uri, name, mimeType}`) introduced in 2025-11-25. Tools return a URI pointer instead of inlining content. Not guaranteed to appear in `resources/list`. Source: [Tools spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools). |
| `icons` (tool/resource/prompt field) | Optional array `{src, mimeType, sizes?[]}` on Tool, Resource, ResourceTemplate, Prompt. Added in 2025-11-25 (SEP-973). Source: [Changelog 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/changelog). |

---

## References

**Designing a new server — the single canonical reading order:**

```
design-philosophy → tool-design → clients → agent-ux → feedback-tool → security-threats → observability
```

Read sequentially. `clients` is third on purpose: it shapes downstream choices (timeouts, async pattern, which notifications to wire) made in `agent-ux`, `feedback-tool`, and `security-threats`. Reading it last means absorbing consequences before constraints. Add stack-specific refs (daemon-architecture, gateway-aggregation) when they match your deployment — see "Load by use case" below. For SDK/framework recipes (Pydantic schema quirks, FastMCP decorator options, etc.) consult upstream docs — those move version-to-version and this skill stays design-level.

**Auditing an existing server:** read [audit-checklist.md](references/audit-checklist.md) first; jump into the linked ref on each ❌ finding rather than re-reading the spine.

**Load by use case:**

| Use case | Read |
|----------|------|
| **Designing a new server end-to-end** | follow the spine above |
| **Auditing** an existing server | audit-checklist plus the UNIVERSAL refs; add conditional refs only when the stack matches |
| **Security review** | security-threats, clients, audit-checklist (§14 Security, §12 Transport and Logging, §5 Parameter Schemas) |
| **Tool-surface review / 80-20 audit** | observability, audit-checklist (§1 Design Philosophy) |
| **Stateful backend** (DB, WebSocket, ML model) | daemon-architecture |
| **Remote multi-server gateway** | gateway-aggregation, security-threats, clients, audit-checklist |

| Reference | Scope | Content |
|-----------|-------|---------|
| [design-philosophy.md](references/design-philosophy.md) | UNIVERSAL | "Not an API wrapper" principles, antipatterns, Bad vs Good comparisons |
| [tool-design.md](references/tool-design.md) | UNIVERSAL | Naming, classification, annotations, outputSchema, parameters, pagination, long-running ops |
| [agent-ux.md](references/agent-ux.md) | UNIVERSAL + OPINIONATED | System prompt, dark-room testing, `Action:` error hints |
| [feedback-tool.md](references/feedback-tool.md) | OPINIONATED | `submit_feedback` interface, CLI contract, data model, when-not-to-use |
| [security-threats.md](references/security-threats.md) | UNIVERSAL | Prompt injection, authn/authz, sessions, DoS, secrets, supply chain |
| [observability.md](references/observability.md) | UNIVERSAL + OPINIONATED | Per-call logging schema, storage patterns, privacy rules, report templates |
| [clients.md](references/clients.md) | EMPIRICAL | Claude Desktop, Claude Code capabilities + timeouts + cross-client matrix — verified 2026-04-28 / 2026-05-22 |
| [audit-checklist.md](references/audit-checklist.md) | MIXED | 16-section, ~80-item checklist; items tagged; HIGH/MEDIUM/LOW output |
| [daemon-architecture.md](references/daemon-architecture.md) | STACK:stateful-backends | Daemon + on-demand split, Unix socket, crash isolation |
| [gateway-aggregation.md](references/gateway-aggregation.md) | STACK:remote-multi-server | Docker MCP Gateway, shared OAuth edge, tool-surface curation |

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

**Choose the right primitive first:**
- Model decides when to invoke it → **Tool**
- Stable, URI-addressable context the client pre-loads → **Resource** (see [tool-design.md §Three Primitives](references/tool-design.md#three-primitives))
- User triggers an explicit reusable workflow by name → **Prompt** (see [tool-design.md §Three Primitives](references/tool-design.md#three-primitives))

**Tool rules:**
- Names: `snake_case`, verb_noun — `list_dialogs`, `get_entity_info`, `submit_feedback`
- `title`: include on every tool `[OPINIONATED]` — spec marks it optional; in practice clients display it as user-facing prose. 1–3 words, product language, sentence case ("Search messages", not `search_messages`)
- `icons`: optional `{src, mimeType, sizes?[]}` array on Tool/Resource/Prompt (SEP-973, 2025-11-25)
- Classify each tool: `primary` (user-facing) or `secondary/helper` (plumbing)
- Annotate explicitly: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
- Mutating tools default to safe states: drafts, paused resources, dry-run, conservative limits
- Declare `outputSchema` on structured tools — when declared, MUST return `structuredContent` on every call (see glossary + tool-design.md)
- Use `isError: true` for business errors (validation, API failures) — never raise protocol exceptions for domain errors
- Error messages must be actionable: include what went wrong + diagnostic detail + `Action:` hint
- Flat parameter schemas — no bare `dict` / `object` without `properties`. Typed nested models with fully-declared `properties` at ≤1 level are fine; ≥2 levels hallucinate regardless of typing. → [tool-design.md §Argument Flattening](references/tool-design.md#argument-flattening)
- Hard-cap all list responses; include pagination token when truncated
- ≤10 primary tools is a signal, not a hard cap *(OPINIONATED — rationale and exceptions in `references/tool-design.md` §Classification)*. Diagnostic tools (`health`, `version`), polling tools paired with async handles or `taskSupport: required`, and the `submit_feedback` channel are *secondary* — they don't count against the ≤10 budget.
- Spec MUST: declare `tools` capability whenever the server exposes tools. Minimum is `"tools": {}`; upgrade to `"tools": {"listChanged": true}` only when your tool set mutates after init (auth gating, feature flags, multi-tenant). Declaring `listChanged: true` on a static surface misleads defenders into watching for events that never fire; delivery across clients is uneven — see [clients.md cross-client matrix](references/clients.md#cross-client-capability-matrix) and [tool-design.md §Dynamic Tool Sets](references/tool-design.md#dynamic-tool-sets--listchanged).

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
- Pair with the system-prompt feedback directive — verbatim text + placement guidance at [agent-ux.md §System Prompt as Configuration Surface](references/agent-ux.md#feedback-directive)

→ Full interface spec including severity, missing_capability, workaround_used, and the complete parameter contract: [references/feedback-tool.md](references/feedback-tool.md)

---

## Agent UX

- Tool descriptions serve two audiences: LLM (reads as prompt) and human (sees in UI). Write for LLM first
- System prompt (`server.instructions`): keep minimal — grow only when you see agents making wrong decisions without the directive. ALL-CAPS named workflow patterns, built dynamically at startup. Canonical ~100-word example covering all four content types: [agent-ux.md §System Prompt as Configuration Surface](references/agent-ux.md#system-prompt-as-configuration-surface)
- Dark-room UX test: agent + server + real task + no briefing → review feedback queue. Copy-paste prompt template: [agent-ux.md §Dark-Room Test](references/agent-ux.md#dark-room-test)
- Error messages: include `Action:` hint for every recoverable error — agents act on error text directly

→ Full patterns: [references/agent-ux.md](references/agent-ux.md)

---

## Daemon + On-Demand Architecture `[STACK:stateful-backends]`

Skip this section unless your backend is stateful or requires shared infrastructure across tool calls.

→ [references/daemon-architecture.md](references/daemon-architecture.md) — daemon/MCP split,
Unix socket rules, crash isolation, when NOT to use this pattern.

---

## Transport

**Default: `stdio`.** Pick a network transport only when a concrete reason rules `stdio` out (multi-process clients on the same host, remote consumers, gateway aggregation, container-network access from sibling containers). `stdio` has no port allocation, no Origin headers, no DNS-rebinding surface, no session-id semantics — pick the simpler thing first.

**Decision tree** (apply in order — first matching branch wins, then keep walking for the auth layer):

- Server launched as a subprocess by Claude Desktop / a CLI host (including local Claude Code via `.mcp.json` with a `command`)? → **`stdio`**
- Remote SaaS endpoint consumed by Claude Code (or any HTTP-capable client) over the public internet? → **Streamable HTTP + TLS + OAuth 2.1** (per-principal, narrow scopes, audience-bound tokens — see [clients.md §Claude Code](references/clients.md#claude-code) for the supported OAuth shape; full requirements in the worked-pairings table below and `security-threats.md §3`)
- Need to be reached by sibling containers / non-subprocess clients on the same host (Docker network, separate host process)? → **Streamable HTTP**
- Exposed outside a trusted network? → **add an auth layer** (OAuth 2.1; tokens MUST include audience claim per RFC 8707 — see [references/security-threats.md](references/security-threats.md))
- Internal Docker network with no untrusted neighbours? → plaintext is acceptable

**Worked pairings** (deployment shape → transport → auth):

| Deployment shape | Transport | Auth |
|------------------|-----------|------|
| Claude Desktop launches your server as a subprocess | `stdio` | none (process boundary) |
| Docker MCP gateway behind shared OAuth edge | `streamable-http` on `0.0.0.0:<port>` inside the docker network | OAuth 2.1 terminated at the gateway, not per backend |
| Remote SaaS server for external users (incl. Claude Code) | `streamable-http` + TLS | OAuth 2.1 per-principal; narrow scopes; audience-bound tokens |

> **Streamable HTTP** (spec 2025-11-25, replacing deprecated HTTP+SSE): single endpoint, POST + GET. Server chooses `application/json` vs `text/event-stream` per response — SSE is for streaming multiple messages on one request, not always-on. Client MUST include `MCP-Protocol-Version: 2025-11-25` header; server SHOULD assume `2025-03-26` if absent, MUST respond 400 if invalid. *(FastMCP / Python `mcp` and `@modelcontextprotocol/sdk-typescript` handle this header negotiation transparently; only matters for raw / framework-direct HTTP implementations.)* `Mcp-Session-Id`: server MAY assign at init; client MUST include thereafter. DNS rebinding: server MUST validate `Origin` header (403 if invalid). Spec says SHOULD bind to localhost rather than `0.0.0.0`; this skill treats it as **MUST for default deployments** — only relax when a private-container-network + auth-gateway pairing makes `0.0.0.0` safe (see worked-pairings table). Strongest mitigation is a Unix domain socket (browsers cannot reach it). Source: [Transports spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).

- **The old HTTP+SSE transport (spec 2024-11-05) is deprecated — never use it**
- `[STACK:remote-multi-server]` Put auth/proxy/ingress in front of a curated gateway, not in every backend server
- For `stdio`, **all logging goes to `stderr`** — `stdout` carries JSON-RPC and any other byte corrupts the transport silently. Canonical rule + daemon-pattern inversion: [references/daemon-architecture.md §Stderr Rule](references/daemon-architecture.md#stderr-rule-reversed-under-this-pattern).

→ Gateway aggregation: [references/gateway-aggregation.md](references/gateway-aggregation.md)
→ Security per transport: [references/security-threats.md](references/security-threats.md)
→ Client capabilities and limitations (Claude Desktop, Claude Code) + cross-client matrix: [references/clients.md](references/clients.md)

---

## Security

- **Prompt injection** — delimit untrusted content in tool responses; never inject raw message/file/DB content
- **Localhost exposure** — bind to `127.0.0.1` or Unix socket; never expose without auth on public interface
- **Annotation trust** — annotations are hints, not security boundaries. Canonical statement + design implications: [tool-design.md §Annotations](references/tool-design.md#annotations)
- **Input boundary** — validate all paths, shell arguments, URLs, tenant IDs, and secrets server-side

→ Threat reference (data injection, authn/authz, sessions, DoS, secrets, supply chain, release stability): [references/security-threats.md](references/security-threats.md)

---

## Observability *(UNIVERSAL + OPINIONATED)*

Per-call logs drive dead-tool / hot-tool / error-rate decisions. Minimum fields: `ts`, `tool_name`, `status`, `duration_ms`. Never log raw args or responses (secrets, PII, prompt-injected content). → [references/observability.md](references/observability.md) for schema, storage patterns, privacy rules, report templates.

---

## Testing and Validation

- Unit tests: cover tool logic and schema validation in isolation
- Integration smoke test: call every tool through the actual transport against a live server
- After any code change: rebuild (if containerised) and run smoke test before marking done
- Green unit tests do not prove the live server works — green smoke test does

**Minimal smoke-test recipes** (run after build, before marking done):

*stdio:* pipe a JSON-RPC `initialize` + `tools/list` through the server binary and assert non-empty `tools` and that **no non-JSON bytes appear on stdout** (see [security-threats.md §Transport choice and stderr](references/security-threats.md#transport-choice-and-stderr) for the stdout-cleanliness one-liner).

*Streamable HTTP:*

```bash
# 1. initialize handshake — expect JSON-RPC result, not 404/500
curl -sS -X POST "$URL" \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-11-25' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'

# 2. tools/list — expect non-empty tools array
curl -sS -X POST "$URL" \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-11-25' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# 3. Origin check — expect 403 from non-allow-listed origin
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$URL" \
  -H 'Origin: http://evil.test' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/list"}'
```

Gateway / multi-server smoke: [gateway-aggregation.md §Smoke test](references/gateway-aggregation.md).

---

## Auditing an Existing Server

→ [references/audit-checklist.md](references/audit-checklist.md) — 16-section, ~80-item checklist,
`*` marks high-priority items, produces HIGH / MEDIUM / LOW findings summary.

---

## Quick Checks

Before shipping or handing off:

- [ ] `title` set on every tool `[OPINIONATED]` — 1–3 words, sentence case, user-facing
- [ ] Tools designed for outcomes, not 1:1 endpoint wrappers
- [ ] Primary tool count scrutinised against the ≤10 signal `[OPINIONATED]` — see tool-design.md §Classification
- [ ] Mutating tools safe by default — draft/paused/dry-run unless explicit activation
- [ ] *(if adopting feedback pattern — see feedback-tool.md §When NOT to use)* `submit_feedback` present `[OPINIONATED]` — write-only, fire-and-forget; system prompt includes feedback directive
- [ ] `outputSchema` declared tools always return `structuredContent` (MUST)
- [ ] Business errors use `isError: true` with actionable diagnostics — no protocol exceptions
- [ ] For `stdio`, logs go to `stderr`, never `stdout`
- [ ] Integration smoke test passes against live server
- [ ] No bare `dict` / `object` without `properties` in parameter schemas; typed nested models OK at ≤1 level
- [ ] Per-call usage log in place — `ts`, `tool_name`, `status`, `duration_ms` minimum; no raw args/responses `[OPINIONATED]`

---

## What's Evolving

Each bullet ends in an action you can take *now*, not "watch this space".

- **MCP Apps** (SEP-1865, announced 2025-11-21): optional backwards-compatible extension adding `ui://` URI scheme, tool→UI metadata linking, sandboxed iframe rendering, bi-directional JSON-RPC over `postMessage`. *Action now:* if your tool returns HTML/JSON intended for rendering, keep `structuredContent` schema-stable so MCP Apps adoption later is a non-breaking addition, not a rewrite. Repo: [modelcontextprotocol/ext-apps](https://github.com/modelcontextprotocol/ext-apps). Blog: [2025-11-21 announcement](https://blog.modelcontextprotocol.io/posts/2025-11-21-mcp-apps/).
- **Sampling deprecated** in DRAFT-2026-v1 (SEP-2596). *Action now:* do not design new servers around `sampling/createMessage`; remove any optimistic capability checks for it.
- **Tasks** (SEP-1686) landed in 2025-11-25 as experimental — per-tool `execution.taskSupport` field; see glossary. *Action now:* declare `taskSupport: optional` on tools that already exceed Claude Desktop's *defensive ~20s guidance* (single 26s observation, not a documented budget — see [clients.md §Claude Desktop §Timeouts](references/clients.md#timeouts)). Reserve `taskSupport: required` until [clients.md cross-client matrix](references/clients.md#cross-client-capability-matrix) shows target clients negotiating `tasks` at `initialize`.

## External References

- [MCP Specification (2025-11-25, stable)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Specification (draft)](https://modelcontextprotocol.io/specification/draft)
- [MCP Docs](https://modelcontextprotocol.io/docs)
