# Agent Feedback Channel — Interface Specification

> Load when implementing `submit_feedback` or the operator CLI. OPINIONATED — maintainer-feedback pattern, not protocol. Language-agnostic contract.

---

## Concept

The agent sees one write-only tool. The operator sees a CLI queue with a lifecycle.
Data flows in one direction — agent → operator. There is no return channel.

---

## MCP Tool: `submit_feedback`

**Canonical annotations** — `destructiveHint: false` is the load-bearing opt-out (asymmetric default; see SKILL.md glossary).

```json
"annotations": {
  "readOnlyHint":   false,
  "destructiveHint": false,
  "idempotentHint": false,
  "openWorldHint":  false,
  "title": "Submit feedback"
}
```

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
| `task` | string | no | 2 000 chars | The user's original request — verbatim preferred. Enables clustering submissions by task type for offline analysis |
| `missing_capability` | string | no | 1 000 chars | What the agent needed but couldn't find. The highest-signal field for new feature decisions |
| `confusing_tool` | string | no | 200 chars | Tool name that was ambiguous, misleading, or had unexpected behaviour |
| `workaround_used` | string | no | 1 000 chars | How the agent worked around the limitation. Two calls where one should suffice = high-signal gap |
| `model` | string | no | 200 chars | Agent model name, e.g. `claude-opus-4-7` |
| `harness` | string | no | 200 chars | Client/environment, e.g. `Claude Desktop`, `Cursor`, `Codex CLI` |

**Response to agent:** plain text confirmation (`"Feedback recorded."` or equivalent). No ID, no status — fire and forget. (Write-only invariant — see Design Principles below.)

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

**Output format per entry** (square brackets and their contents are omitted when the field is absent):
```
id=<N> [severity=<...>] [status=<...>] <YYYY-MM-DD HH:MM> [changed=<YYYY-MM-DD HH:MM>] [model=<...>] [harness=<...>]
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
| `task` | agent | nullable; user's original request for clustering |
| `missing_capability` | agent | nullable; highest-signal field for new-feature decisions |
| `confusing_tool` | agent | nullable; offending tool name |
| `workaround_used` | agent | nullable; describes the gap |
| `model` | agent | nullable |
| `harness` | agent | nullable |
| `status` | operator | default: `open` |
| `status_changed_at` | operator | nullable unix timestamp |
| `status_comment` | operator | nullable; set via `--reason` |

This schema is open — richer signal fields (`task`, `missing_capability`, `confusing_tool`,
`workaround_used`) extend the row alongside `message`/`context`. Treat the column set as
additive; do not strip the agent-visible Parameters table down to a "core five".

### Reference DDL (SQLite)

```sql
CREATE TABLE feedback (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  submitted_at        INTEGER NOT NULL,                          -- unix epoch seconds
  message             TEXT    NOT NULL CHECK (length(message) BETWEEN 1 AND 10000),
  severity            TEXT             CHECK (severity IN ('bug','suggestion','question')),
  context             TEXT             CHECK (length(context) <= 2000),
  task                TEXT             CHECK (length(task) <= 2000),
  missing_capability  TEXT             CHECK (length(missing_capability) <= 1000),
  confusing_tool      TEXT             CHECK (length(confusing_tool) <= 200),
  workaround_used     TEXT             CHECK (length(workaround_used) <= 1000),
  model               TEXT             CHECK (length(model) <= 200),
  harness             TEXT             CHECK (length(harness) <= 200),
  status              TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','done','dismissed')),
  status_changed_at   INTEGER,
  status_comment      TEXT
);
CREATE INDEX idx_feedback_status_submitted ON feedback (status, submitted_at DESC);
```

Postgres: replace `INTEGER PRIMARY KEY AUTOINCREMENT` with `BIGSERIAL PRIMARY KEY`, `INTEGER` timestamps with `TIMESTAMPTZ`, `TEXT CHECK length` with `VARCHAR(N)`. CHECK constraints on `severity` / `status` are load-bearing — they're the on-disk enforcement of the lifecycle table above.

---

## Design Principles

1. **Write-only for the agent.** No `get_feedback` tool, no tracking ID in the response.
2. **Fire and forget.** Agent gets acknowledgement of recording, not of resolution.
3. **Separate storage.** Feedback does not share a table/file with the server's main data.
   This lets the operator read it independently without locking the main data store.
4. **Daemon is sole writer** (if the server has a daemon/process split). The operator CLI
   reads the storage directly, read-only. WAL mode (SQLite) or equivalent lets them coexist.
5. **Operator does not respond to the agent.** The feedback loop closes through future
   releases, not in-band replies.

---

## When NOT to use

This pattern is not universally applicable. Avoid `submit_feedback` in these contexts:

- **Adversarial environments** — Feedback is an injection surface. Anything the agent writes may be replayed to maintainers reading the queue, or back to future agent sessions acting as prompts.
- **No maintainer reviewing the queue** — Without active review, the feedback queue becomes write-only garbage with no operational value.
- **Short-lived deployments** — Development containers, ephemeral test services, or demo instances torn down before anyone reads the feedback.
