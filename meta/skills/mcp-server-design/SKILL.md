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

SDK setup, scaffolding, language idioms → [`mcp-builder`](https://github.com/anthropics/skills/tree/main/skills/mcp-builder).

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

| Term | Design meaning |
|------|----------------|
| `stdio` / `Streamable HTTP` | The two MCP transports. Pick by who-launches-whom — see §Transport. |
| **Resource** | A primitive *selected and injected by the client*, not invoked by the model. Use when context is stable and URI-addressable. → [tool-design.md §Picking a Primitive](references/tool-design.md#picking-a-primitive--tool-resource-or-prompt) |
| **Prompt** | A primitive *the user* invokes by name (slash command in Claude Code). Use for reusable workflows the user explicitly triggers. → [tool-design.md §Picking a Primitive](references/tool-design.md#picking-a-primitive--tool-resource-or-prompt) |
| `outputSchema` + `structuredContent` | Server contract: declaring `outputSchema` makes `structuredContent` MUST on every successful call. Declare for any tool returning machine-parseable data; always pair with a compact text preview. Owner for nullable / null-arm / `additionalProperties` rules: [tool-design.md §Schema Compatibility](references/tool-design.md#schema-compatibility-gotcha-anyof-with-null). |
| `isError` | The right channel for *business / validation* errors (agent self-corrects). Protocol exceptions are for malformed requests, not domain failures. |
| Tasks (SEP-1686) | Spec primitive for long-running ops. **Status today:** no tracked client negotiates it (matrix shows `⚠️ not declared / unverified` across both Claude clients — see [clients.md](references/clients.md#cross-client-capability-matrix)). Working default is the roll-your-own async handle. Switch to the spec primitive when the matrix flips. → [tool-design.md §Long-Running Operations](references/tool-design.md#long-running-operations). |
| `_meta` | Spec-defined open-ended object on requests / results / tool definitions. Vendor-specific knobs ride here when the spec hasn't standardised them yet — e.g. Claude Code's `anthropic/maxResultSizeChars` is a tool-definition annotation, not inside `_meta` (see [clients.md](references/clients.md)). When in doubt: tool-level knobs go on the tool definition; per-call hints go in request `_meta`; per-result hints in result `_meta`. |
| `server.instructions` | Server-declared system prompt — a config surface for shaping agent behaviour without adding tools. Keep it tight; budget rules in [agent-ux.md](references/agent-ux.md#system-prompt-as-configuration-surface). SDK wiring: FastMCP `instructions=` constructor arg; TypeScript SDK `Server` `instructions` field at construction. Smoke-test it lands by reading `result.instructions` from your initialize probe. |
| Tool `annotations` | Posture hints (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title`) — advisory, not security. **Asymmetric default:** `destructiveHint` defaults to `true` (opt-out). Forgetting to set it to `false` on an additive write (e.g. `submit_feedback`) silently marks the tool destructive. → [tool-design.md §Annotations](references/tool-design.md#annotations). |
| `posture` (primary / secondary) | Project-level classification used by this skill (not a protocol field). Primary = user-facing capability; secondary = plumbing. Drives the ≤10 budget. |
| `resource_link` | Tool result type that returns a URI pointer instead of inlining content. Design use: large payloads, already-addressable resources. Not guaranteed to appear in `resources/list`. |
| `icons` | Optional icon array on Tool/Resource/Prompt. Pure presentation — design implication only when targeting clients that render them. |

---

## References

**Designing a new server:** spine = `design-philosophy → tool-design → clients → agent-ux → feedback-tool → security-threats → observability`. Add `daemon-architecture` for stateful backends; add `gateway-aggregation` for multi-server-behind-one-edge.
**Auditing an existing server:** start at `audit-checklist.md` and jump to the linked ref on each `❌` finding.

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
| [daemon-architecture.md](references/daemon-architecture.md) | STACK:stateful-backends | Daemon + on-demand split, Unix socket, crash isolation. **Canonical owner of the stderr rule** (linked from every transport callout — load this ref to read the rule even on stateless servers). |
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
- Stable, URI-addressable context the client pre-loads → **Resource** (see [tool-design.md §Picking a Primitive](references/tool-design.md#picking-a-primitive--tool-resource-or-prompt))
- User triggers an explicit reusable workflow by name → **Prompt** (see [tool-design.md §Picking a Primitive](references/tool-design.md#picking-a-primitive--tool-resource-or-prompt))

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

**Decision tree.** Disambiguate first: **is the client launching the server (subprocess), or connecting to a long-lived endpoint?** First matching branch wins, then keep walking for the auth layer.

- Client launches the server as a subprocess (Claude Desktop; Claude Code via `.mcp.json` with `"command"`; any CLI host)? → **`stdio`**. Same-machine, single-consumer, no port allocation, no Origin/DNS-rebinding surface.
- Client connects to a long-lived endpoint? → **Streamable HTTP**. Pick the auth shape by *who reaches the endpoint*:
  - Public internet, multiple/external users → **TLS + OAuth 2.1 per-principal, narrow scopes, audience-bound tokens** (RFC 8707). See `security-threats.md §3`.
  - Private network only (Tailscale, internal VPN, sibling containers) — single trusted user → TLS optional inside the trusted network; a single shared token is acceptable.
  - Internal Docker network with no untrusted neighbours → plaintext + auth terminated at a gateway (worked pairing row 2 below).

**Worked pairings:**

| Deployment shape | Transport | Auth |
|------------------|-----------|------|
| Claude Desktop / local Claude Code launches your server as a subprocess | `stdio` | none (process boundary) |
| Docker MCP gateway behind shared OAuth edge | `streamable-http` on `0.0.0.0:<port>` inside the docker network | OAuth 2.1 terminated at the gateway, not per backend |
| Personal / single-user server behind Tailscale, VPN, or private LAN | `streamable-http` (TLS if crossing untrusted hops) | single bearer token tied to the principal, or none on a fully trusted network |
| Remote SaaS server for external users (incl. remote Claude Code) | `streamable-http` + TLS | OAuth 2.1 per-principal; narrow scopes; audience-bound tokens |

**Streamable HTTP** = MCP's current HTTP transport (spec 2025-11-25): one endpoint accepting POST + GET, server picks `application/json` or `text/event-stream` per response. Replaces the deprecated HTTP+SSE transport (2024-11-05). **Design-binding rules** (the rest of the protocol shape is in the spec):

- Server MUST validate `Origin` (403 if invalid). FastMCP / Python `mcp` and TS SDK do this by default; verify it's not disabled. Allow-list must match what your client actually sends.
- Bind to localhost (not `0.0.0.0`) by default — relax only for the docker-network + auth-gateway pairing in the table above. Unix domain socket is the strongest mitigation (browsers cannot reach it).
- The old HTTP+SSE transport (spec 2024-11-05) is deprecated — never use it.
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

# 2. notifications/initialized — required by spec before any other request
curl -sS -X POST "$URL" \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-11-25' \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

# 3. tools/list — expect non-empty tools array
curl -sS -X POST "$URL" \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-11-25' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# 4. Origin check — expect 403 from non-allow-listed origin
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

- [ ] `title` set on every tool `[OPINIONATED]` — 1–3 words, sentence case, user-facing. *Skip when:* no target client surfaces `title` distinctly from `name`.
- [ ] Tools designed for outcomes, not 1:1 endpoint wrappers
- [ ] Primary tool count scrutinised against the ≤10 signal `[OPINIONATED]` — see [tool-design.md §Tool Classification](references/tool-design.md#tool-classification--primary-vs-secondary-and-the-10-tool-signal). *Skip when:* surface intentionally domain-broad with prefix namespacing across many tools — namespacing carries the load instead.
- [ ] Mutating tools safe by default — draft/paused/dry-run unless explicit activation
- [ ] *(if adopting feedback pattern — see feedback-tool.md §When NOT to use)* `submit_feedback` present `[OPINIONATED]` — write-only, fire-and-forget; system prompt includes feedback directive. *Skip when:* no maintainer reads the queue, deployment is short-lived/demo, or environment is adversarial.
- [ ] `outputSchema` declared tools always return `structuredContent` (MUST)
- [ ] Business errors use `isError: true` with actionable diagnostics — no protocol exceptions
- [ ] For `stdio`, logs go to `stderr`, never `stdout`
- [ ] Integration smoke test passes against live server
- [ ] No bare `dict` / `object` without `properties` in parameter schemas; typed nested models OK at ≤1 level
- [ ] Per-call usage log in place — `ts`, `tool_name`, `status`, `duration_ms` minimum; no raw args/responses `[OPINIONATED]`. *Skip when:* pre-production / dev server with no real traffic — treat as debt to clear before first production deploy.

---

## What's Evolving

- **If your tool returns HTML/JSON for rendering — keep `structuredContent` schema-stable.** MCP Apps ([SEP-1865](https://github.com/modelcontextprotocol/ext-apps)) is rolling out a `ui://` rendering extension; stable schemas keep its later adoption non-breaking.
- **Do not design new servers around `sampling/createMessage`.** Deprecated protocol-wide; remove optimistic capability checks.
- **Long-running tools today: roll-your-own async handle is the working mechanism; `taskSupport: optional` is a future-leaning hedge.** `taskSupport` (per-tool flag) is a no-op on clients that don't negotiate the `tasks` capability — and no client tracked in [clients.md](references/clients.md#cross-client-capability-matrix) does today. For Claude Desktop's defensive ~20s ceiling (single 26s observation — see [clients.md §Timeouts](references/clients.md#timeouts)), only the roll-your-own pattern protects you; declaring `taskSupport: optional` alongside is harmless and switches on automatically when clients catch up. Reserve `taskSupport: required` until the matrix flips.

## External References

- [MCP Specification (2025-11-25, stable)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Specification (draft)](https://modelcontextprotocol.io/specification/draft)
- [MCP Docs](https://modelcontextprotocol.io/docs)
