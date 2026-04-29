# Agent Feedback Channel — Interface Specification

> **Load when:** Implementing `SubmitFeedback` or the operator feedback CLI in any MCP server.

Language-agnostic contract. Implement in Python, TypeScript, Go, or whatever the server is written in.

---

## Concept

The agent sees one write-only tool. The operator sees a CLI queue with a lifecycle.
Data flows in one direction — agent → operator. There is no return channel.

---

## MCP Tool: `SubmitFeedback`

**Type:** write (`readOnlyHint: false`)

**When the agent should call it** — write this into the tool description verbatim:
- A tool returned unexpected or incorrect output
- An error message is unclear or doesn't help fix the situation
- A capability was needed but didn't exist
- A tool's behaviour contradicts its documentation

**Parameters:**

| Field | Type | Required | Limit | Description |
|-------|------|----------|-------|-------------|
| `message` | string | yes | 1–10 000 chars | What was observed; ideally what was expected instead |
| `severity` | enum | no | — | `bug` — wrong output or violated contract; `suggestion` — new capability or UX improvement; `question` — unclear how something is supposed to work |
| `context` | string | no | 2 000 chars | Which tool, what arguments, or general context the agent was operating in |
| `task` | string | no | 2 000 chars | The user's original request — verbatim preferred. Enables clustering by task type. Also populated automatically if the server has a `declare_session_task` tool |
| `missing_capability` | string | no | 1 000 chars | What the agent needed but couldn't find. The highest-signal field for new feature decisions |
| `confusing_tool` | string | no | 200 chars | Tool name that was ambiguous, misleading, or had unexpected behaviour |
| `workaround_used` | string | no | 1 000 chars | How the agent worked around the limitation. Two calls where one should suffice = high-signal gap |
| `model` | string | no | 200 chars | Agent model name, e.g. `claude-opus-4-7` |
| `harness` | string | no | 200 chars | Client/environment, e.g. `Claude Desktop`, `Cursor`, `Codex CLI` |

**Response to agent:** plain text confirmation (`"Feedback recorded."` or equivalent).
No ID, no status — fire and forget.

**Invariant:** no tool exists for the agent to read feedback back. This is intentional —
it avoids creating the illusion of a dialogue where there is none.

---

## Operator CLI

Subcommand `feedback` nested under the server's main CLI entry point.

### `feedback list`

```
<server> feedback list [--limit N] [--all]
```

Default: shows only `open` and `in_progress`, newest first. This is "what needs attention".

`--all` adds `done` and `dismissed` to the view (history).

`--limit N` caps rows returned (default: 50).

**Output format per entry:**
```
id=<N> [<severity|?>] [<status>] <YYYY-MM-DD HH:MM> [changed=<YYYY-MM-DD HH:MM>] [model=<...>] [harness=<...>]
  message: <text>
  context: <text>         ← only if present
  status_comment: <text>  ← only if present
```

Empty queue with history: `No open or in-progress feedback. Use --all to show history.`

### `feedback status <id> <status> [--reason "..."]`

```
<server> feedback status 42 in_progress --reason "Reproduced, investigating"
<server> feedback status 42 done        --reason "Fixed in v1.3"
<server> feedback status 42 dismissed   --reason "Expected behaviour, updating docs"
```

**Status lifecycle:**

```
open  →  in_progress  →  done
                      →  dismissed
```

`--reason` is optional but recommended — it makes the queue readable as a history.

### `feedback delete <id>`

Removes the row permanently. Use for spam or test submissions.

---

## Data Model

| Field | Source | Notes |
|-------|--------|-------|
| `id` | system (autoincrement) | — |
| `submitted_at` | system (unix timestamp) | set at ingestion |
| `message` | agent | required |
| `severity` | agent | nullable |
| `context` | agent | nullable |
| `model` | agent | nullable |
| `harness` | agent | nullable |
| `status` | operator | default: `open` |
| `status_changed_at` | operator | nullable unix timestamp |
| `status_comment` | operator | nullable; set via `--reason` |

---

## Session-Level Task Tracking (Optional Enhancement)

For servers where understanding *what the agent was trying to accomplish* matters as much
as *what went wrong*, add a `declare_session_task` tool alongside `SubmitFeedback`.

**Protocol:**

1. Agent calls `declare_session_task(task=<user's request verbatim>)` before any other tool
2. Agent does its work — the server auto-correlates all tool calls to the declared task
3. Agent calls `SubmitFeedback(...)` with observations at end of session

**Why verbatim:** agents paraphrase naturally. The original user request captures intent
that rephrasings lose. Instruct the agent: *"Pass the user's exact words, not your
interpretation."*

**`declare_session_task` tool spec:**

- Parameters: `task` (string, required, 2 000 chars) — the user's request
- Response: plain confirmation. No session ID returned — the server tracks the active
  connection internally and attaches the declared task to all subsequent calls and feedback
- Annotations: `readOnlyHint: true`, `destructiveHint: false`
- Posture: `secondary/helper` — plumbing, not a primary capability

**What structured task tracking unlocks (for the proposer/optimizer):**

| Pattern | What it reveals |
|---------|----------------|
| Task X → `search_*` called twice with different args | Missing filter parameter for X use cases |
| Task X → `missing_capability` populated in >50% of sessions | Clear feature gap for X |
| Task X → `workaround_used` mentions tool Y | Y should absorb the extra step, or grow a param |

**Implicit trace signals (no tool required):**

Even without explicit feedback, server-side call traces are signal:
- Two `search_*` calls with different args in one session → first result insufficient
- Error on first call → retry with adjusted args → description ambiguity or param semantics

The declare/feedback pair enriches these patterns with task context for offline analysis.

---

## Design Principles

1. **Write-only for the agent.** No `GetFeedback` tool, no tracking ID in the response.
2. **Fire and forget.** Agent gets acknowledgement of recording, not of resolution.
3. **Separate storage.** Feedback does not share a table/file with the server's main data.
   This lets the operator read it independently without locking the main data store.
4. **Daemon is sole writer** (if the server has a daemon/process split). The operator CLI
   reads the storage directly, read-only. WAL mode (SQLite) or equivalent lets them coexist.
5. **Operator does not respond to the agent.** The feedback loop closes through future
   releases, not in-band replies.
