# Agent UX Reference

> Load when writing tool descriptions, designing `server.instructions`, or running UX validation. Tool descriptions + `Action:` errors are UNIVERSAL; system prompt structure, dark-room testing, and feedback loops are OPINIONATED.

---

## Tool Description Structure

```
One-sentence summary (what the tool does, present tense).

LLM guidance: when to call (triggers, proactive conditions),
what the output means, what NOT to do, field semantics in prose.
```

The one-liner doubles as the human tooltip; the LLM reads the entire block.

---

## What Actually Moves Tool Selection

Description content moves tool selection; structural tags don't. Levers, in rough order of impact:

| Lever | What it is | Lives in |
|-------|------------|----------|
| **Assertive proactive language** | "Use this **proactively** whenever the agent notices X" inside the description | `tool-design.md §Writing Tool Descriptions` |
| **Namespacing in the tool name** | Service prefix on the identifier — `asana_search`, `jira_search` | `tool-design.md §Naming` |
| **Sharper, distinct descriptions** | Each description semantically distant from others; near-duplicates collapse selection | `tool-design.md §Writing Tool Descriptions` |
| **Formal MCP annotations** | `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` (plus `title` — surfaced in annotations by some SDKs, top-level on `Tool` per spec) | `tool-design.md §Annotations` |
| **Toolsets / config-level grouping** | Let operators enable/disable groups at install time (e.g. GitHub MCP `--toolsets`) | organisational pattern |

Do not prefix descriptions with `[primary]` / `[secondary/helper]` — not a validated lever.

> Evidence: Faghih et al. 2025 — *Tool Preferences in Agentic LLMs are Unreliable* (arxiv.org/abs/2505.18135); Anthropic — *Writing tools for agents*.

---

## System Prompt as Configuration Surface

The system prompt (`server.instructions` in MCP) is a first-class knob for shaping
agent behaviour without adding tools. It's sent at `initialize` (once per session),
then folded into the host's system prompt for the rest of the conversation — keep it tight.

**What belongs here:**

| Type | Example |
|------|---------|
| Domain authority | "Read-only access to message history via a local sync cache." |
| Named workflow patterns | "SEARCH THEN READ: use search_messages to find, then list_messages to read context" |
| Stable context hints | "`dialog_id` is stable for the session — cache it, don't re-resolve on every call" |
| Feedback directive | <a id="feedback-directive"></a>"Use `submit_feedback` immediately when a tool response is wrong, surprising, or missing a useful capability — don't wait until end of session." |
| Error recovery hints | "If get_entity_info returns access_error, the dialog may need mark_dialog_for_sync first" |

**What does NOT belong here:** parameter docs, field walkthroughs, data that changes
between requests (those are tool responses).

**Canonical example — maximum shape.** Your server should start with only the types you observed agents needing (budget principle below). Treat the shape, not the wording, as the template.

```
Read-only access to message history via a local sync cache. If results look stale,
call `get_sync_status` to check lag; `mark_dialog_for_sync` refreshes a dialog.

Connected account: id=42, name="Mila".

Key workflows:
- SEARCH THEN READ: `search_messages` (omit dialog= for global) finds hits;
  `list_messages(anchor_message_id=M)` reads context around any hit.
- BROWSE: `list_messages` with navigation="newest" or a next_navigation token;
  continue until next_navigation is absent.
- FIND DIALOG IDS: `list_dialogs` returns exact numeric dialog ids.

`dialog_id` is stable for the session — cache it, don't re-resolve on every call.

Use `submit_feedback` immediately when a tool response is wrong, surprising, or
missing a useful capability — don't wait until end of session.
```

**Format rule for the workflow section:** ALL-CAPS labels, one named pattern per line.

**Dynamic data injection:** build the system prompt at startup, not at deploy time. Inject live server state (connected account, current limits, active features) so the agent has accurate context without a dedicated info tool.

```python
# Python / FastMCP example — [STACK:Python, daemon-architecture]
# The daemon_connection() call assumes the daemon + on-demand split.
# For non-daemon servers, fetch live state with whatever client you already use.
async def _build_server_instructions() -> str:
    base = "Static guidance..."
    try:
        async with daemon_connection() as conn:
            data = (await conn.get_me())["data"]
        base += f' Connected account: id={data["id"]}, name="{name}".'
    except Exception:
        pass  # degrade gracefully
    return base
```

**Budget principle:** the instructions occupy real estate in the host's system prompt for the entire conversation, so they compete with the user's own context. Start minimal — add a directive only when you observe agents making the wrong decision without it. If the system prompt keeps growing, a missing tool is probably the real fix, not more text.

---

## Error Messages with `Action:` Hints

Agents act on error text directly. A good error message includes what went wrong
**and what to do next**.

```
# Bad
"Entity not found"

# Good
"Entity 12345 not found — use `list_dialogs` to get valid dialog ids."

# Good (boundary error pattern)
"Tool `get_entity_info` argument validation failed: field 'dialog_id' required.
 Action: Check the tool arguments against the exported schema and retry."
```

The `Action:` suffix is a reliable pattern: it's machine-readable enough that
agents can parse the instruction, and human-readable enough to be useful in logs.

Apply at both layers:
- **Tool descriptions**: explain what to do when the result is unexpected
- **Error responses**: include an `Action:` line whenever the error is recoverable

---

## Two Kinds of Testing

These address different failure modes and are run at different points in the lifecycle.
Both require `submit_feedback` deployed and the feedback directive in the system prompt.

**Dark-room** = "does it function when the agent is blind?" — a smoke test run after
every significant change. **Agent CustDev** = "does the agent's strategy match the
designer's intent?" — an API design review run once after the first complete surface,
then after major redesigns.

### Dark-Room Test

Give the agent the server with no briefing, assign a real task, then read the feedback queue.

**Dark-room prompt template** — paste verbatim into a fresh agent session with
your target MCP server connected. No briefing, no tool walkthrough.

```
You have been given access to an MCP server. You have not been briefed on what
it does, what tools it exposes, or what conventions it follows. Discover that
yourself from the tool list and descriptions as you work.

Task: <a real user-style task — e.g. "find my unread messages from this week",
"summarise what I was discussing with Mila yesterday", "draft a reply to the
last support ticket I received">.

Meta-instructions:
- Use `submit_feedback` proactively, in the moment, for anything surprising,
  confusing, missing, ambiguous, or wrong. Quote what you tried, name the tool,
  and say what you expected vs. got.
- Do not ask me for clarification about the server itself. Treat unclear tool
  behaviour as feedback, not as a question for me.
- When you finish (or get stuck), submit one final `submit_feedback` titled
  "session summary": what felt intuitive, what was a WTF moment, what capability
  you wished existed but didn't.
```

After the session, review `<server> feedback list`.

**Signals to look for:**

- **Confusing names** — agent tried to call a tool that doesn't exist because the name implied it should
- **Ambiguous descriptions** — agent passed wrong values or misread field semantics
- **Missing error recovery** — error with no `Action:` hint; agent stalled
- **Redundant round-trips** — agent called three tools to do what one should do
- **Reached-for capabilities** — clear signal for the next iteration
- **Contract violations** — agent expected one behaviour, got another

**When to run:** after any significant change to the tool surface — per change, not per release.

**Continuous variant.** With `submit_feedback` deployed and the feedback directive in `server.instructions`, every production session becomes a dark-room test automatically. Instruct the agent to populate `submit_feedback.task` with the user's original request verbatim — that clusters submissions by task type for later review. Gating: active maintainer, non-adversarial environment, long-enough deployment lifetime ([feedback-tool.md §When NOT to use](feedback-tool.md#when-not-to-use)).

### Agent CustDev

Run a dedicated session where capable agents review the API itself — no task, explicitly
about the tool surface. Different models expose different blind spots; use at least two.

**Protocol:**

1. Present the full tool surface to one or more capable agents
2. Ask explicitly: *"Look at these tools as a user who has never used this server.
   For each tool: does the name immediately tell you what it does and when to call it?
   Are there parameters that seem redundant, misnamed, or missing? Is there anything
   you'd expect to exist that isn't here? Would you ever confuse two of these tools?"*
3. Ask about parameter sets specifically: *"Which parameters feel natural to fill in?
   Which ones require you to stop and think? Which ones have ambiguous semantics?"*
4. Ask about descriptions: *"Which descriptions make you more confident about when to call?
   Which ones leave room for misuse?"*
5. Collect responses, look for convergence — if two different agents flag the same tool
   or parameter, it's a real issue

**Goal:** cognitive congruence — tool names, parameter names, and descriptions match
the way a capable agent naturally thinks in this domain. A tool is well-named if an
agent reaches for it without being told to. A parameter is well-structured if filling
it in feels like completing a thought, not consulting a spec.

**When to run:** once after the first complete tool surface; again after any major
redesign. This is a design review, not a QA step — run it before the surface stabilises.

