# Agent UX Reference

> **Load when:** Writing tool descriptions, designing the system prompt, or running
> UX validation on a completed MCP server.
>
> **Scope:** tool descriptions and actionable errors are UNIVERSAL. System prompt structure,
> dark-room testing, and feedback loops are opinionated production practices.

---

## Two Audiences for Every Tool Description

Tool name + description reaches two distinct readers:

| Reader | Where | What they need |
|--------|-------|----------------|
| **LLM (agent)** | reads at inference to decide when/how to call | When to call, what NOT to do, how to interpret output |
| **Human (operator/user)** | sees it in client UIs — tool panels, hover tooltips | What the tool does in one sentence, side effects |

Write for the LLM first — it's the harder constraint. A description precise enough
for an LLM (when to call, what NOT to do, field semantics) is scannable enough for
humans too; the reverse is not reliable.

**Structure that satisfies both:**

```
One-sentence human summary.

LLM guidance: when to call (triggers, proactive conditions),
what the output means, what not to do, field semantics in prose.
```

The one-liner is what humans scan. The LLM reads the entire block.

---

## What Actually Moves Tool Selection *(empirically validated)*

Tool selection is dominated by **description content**, not structural tags. Faghih
et al. (EMNLP 2025) tested nine description-edit types across 17 models on BFCL and
showed that small, surface-level edits to descriptions move selection rates more than
any structural change they measured — descriptions are the single strongest lever an
MCP author has. There is **no evidence** that structural prefix tags like
`[primary] ` / `[secondary/helper] ` change selection. Use the levers below instead.

| Lever | What it is | Where it lives in this skill |
|-------|-----------|------------------------------|
| **Assertive proactive language** | "Use this **proactively** whenever the agent notices X" inside the description | `tool-design.md §Writing Tool Descriptions` (the three-question structure), Faghih et al. found this single most effective |
| **Namespacing in the tool name** | Service prefix on the identifier — `asana_search`, `jira_search` | `tool-design.md §Naming` line 46 (Anthropic engineering recommendation) |
| **Formal MCP annotations** | `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title` — the protocol's own posture channel | `audit-checklist.md §3 Tool Annotations` |
| **Sharper, distinct descriptions** | Each tool's description is semantically distant from others; near-duplicates collapse selection | `tool-design.md §Writing Tool Descriptions` — answer "When?" / "What?" / "What NOT?" |
| **Toolsets / config-level grouping** | Let operators enable/disable groups of tools at install time | GitHub MCP `--toolsets`; an organizational pattern, not a description pattern |

> Background: [Anthropic — Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents);
> [Faghih et al. 2025 — Tool Preferences in Agentic LLMs are Unreliable](https://arxiv.org/abs/2505.18135);
> [MCP tool annotations reference](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

If you're tempted to add a `[primary]` / `[secondary/helper]` prefix to descriptions:
that is **not** the validated lever. Spend the same effort on the description body
(assertive triggers, clearer "What NOT to do", or sharper wording that differentiates
this tool from siblings).

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

**Format: named workflow patterns in ALL-CAPS, one per line.**

```
Key workflows:
- SEARCH THEN READ: Use `search_messages` (omit dialog= for global) to find. Use
  `list_messages(anchor_message_id=M)` to read context around any hit.
- BROWSE: Use `list_messages` with navigation="newest" or a next_navigation token.
  Continue calling until next_navigation is absent.
- FIND DIALOG IDS: Use `list_dialogs` to get exact numeric dialog ids.
```

Named patterns give the LLM stable, compact vocabulary to refer to multi-step flows.
A labelled pattern is easier to retrieve and reason about than re-deriving the steps
from scratch. Measure whether agents cite the labels back on your own surface — the
benefit is strongest on complex multi-step flows where step order matters.

**Dynamic data injection:** build the system prompt at startup, not at deploy time.
Inject live server state (connected account, current limits, active features) so
the agent has accurate context without a dedicated info tool.

```python
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

**Protocol:**

1. Give the agent a **real task** (not a toy: "find my unread messages from this week",
   "summarise what I was discussing with X yesterday")
2. No briefing — don't explain tools, names, or conventions
3. Instruction: *"As you work, use `submit_feedback` for anything surprising, confusing,
   or missing. At the end, submit a session summary: what felt intuitive, what was a
   WTF moment, what capability you wished existed."*
4. Let it run
5. Review `<server> feedback list` after the session

**Signals to look for:**

- **Confusing names** — agent tried to call a tool that doesn't exist because the name implied it should
- **Ambiguous descriptions** — agent passed wrong values or misread field semantics
- **Missing error recovery** — error with no `Action:` hint; agent stalled
- **Redundant round-trips** — agent called three tools to do what one should do
- **Reached-for capabilities** — clear signal for the next iteration
- **Contract violations** — agent expected one behaviour, got another

**When to run:** after any significant change to the tool surface — per change, not per release.

### Agent CustDev

Run a dedicated session where capable agents review the API itself — no task, explicitly
about the tool surface. Different models expose different blind spots; use at least two.

**Protocol:**

1. Present the full tool catalogue to one or more capable agents
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

---

## The submit_feedback + System Prompt Combination

A useful pattern for servers with an active maintainer: the system prompt instructs
agents to submit feedback proactively (the canonical directive line is in the
[System Prompt table](#feedback-directive) above), which turns every production session
into a dark-room test automatically. This works well when there is someone regularly
reviewing the feedback queue.

The operator reviews the queue async, no ceremony required. Over time the feedback
queue becomes a signal for what to fix next.

For clustering submissions by task type, instruct the agent to populate the `task`
field of `submit_feedback` with the user's original request verbatim
(see `feedback-tool.md` parameter table).

**Do not deploy this pattern blindly.** It assumes an active maintainer, a non-adversarial
environment, and a deployment lifetime long enough for review cycles to matter. See
[feedback-tool.md §When NOT to use](feedback-tool.md#when-not-to-use).
