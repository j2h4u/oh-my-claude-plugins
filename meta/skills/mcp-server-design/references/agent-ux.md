# Agent UX Reference

> **Load when:** Writing tool descriptions, designing the system prompt, or running
> UX validation on a completed MCP server.

---

## Two Audiences for Every Tool Description

Tool name + description reaches two distinct readers:

| Reader | Where | What they need |
|--------|-------|----------------|
| **LLM (agent)** | reads at inference to decide when/how to call | When to call, what NOT to do, how to interpret output |
| **Human (operator/user)** | sees it in client UIs — tool panels, hover tooltips | What the tool does in one sentence, side effects |

Write for the LLM first — it's the harder constraint. An LLM-optimal description
is also informative to humans; the reverse is not guaranteed.

**Structure that satisfies both:**

```
One-sentence human summary.

LLM guidance: when to call (triggers, proactive conditions),
what the output means, what not to do, field semantics in prose.
```

The one-liner is what humans scan. The LLM reads the entire block.

---

## The `[posture]` Prefix

The registration posture label (`primary`, `secondary/helper`) is prepended to the
tool description as `[primary] ` or `[secondary/helper] `. The LLM sees this prefix
and uses it to gauge centrality — which tools to reach for first vs. which are
supporting utilities. Keep it consistent.

**Note:** this is a project-local convention, not an MCP spec feature or community standard.
Adopt it if it suits your codebase; skip it if it adds noise for your use case.

---

## System Prompt as Configuration Surface

The system prompt (`server.instructions` in MCP) is a first-class knob for shaping
agent behaviour without adding tools. Every request pays the token cost — keep it tight.

**What belongs here:**

| Type | Example |
|------|---------|
| Domain authority | "Read-only access to message history via a local sync cache." |
| Named workflow patterns | "SEARCH THEN READ: use SearchMessages to find, then ListMessages to read context" |
| Stable context hints | "`dialog_id` is stable for the session — cache it, don't re-resolve on every call" |
| Feedback directive | "Use SubmitFeedback immediately when a tool response is wrong, surprising, or missing a useful capability — don't wait until end of session" |
| Error recovery hints | "If GetEntityInfo returns access_error, the dialog may need MarkDialogForSync first" |

**What does NOT belong here:** parameter docs, field walkthroughs, data that changes
between requests (those are tool responses).

**Format: named workflow patterns in ALL-CAPS, one per line.**

```
Key workflows:
- SEARCH THEN READ: Use SearchMessages (omit dialog= for global) to find. Use
  ListMessages(anchor_message_id=M) to read context around any hit.
- BROWSE: Use ListMessages with navigation="newest" or a next_navigation token.
  Continue calling until next_navigation is absent.
- FIND DIALOG IDS: Use ListDialogs to get exact numeric dialog ids.
```

Named patterns give the LLM stable vocabulary to refer to internally. Agents
will literally invoke "the SEARCH THEN READ workflow" in their reasoning.

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

**Budget principle:** every token in the system prompt is paid per request. Start minimal — add a directive only when you observe agents making the wrong decision without it. If the system prompt keeps growing, a missing tool is probably the real fix, not more text.

---

## Error Messages with `Action:` Hints

Agents act on error text directly. A good error message includes what went wrong
**and what to do next**.

```
# Bad
"Entity not found"

# Good
"Entity 12345 not found — use ListDialogs to get valid dialog ids."

# Good (boundary error pattern)
"Tool GetEntityInfo argument validation failed: field 'dialog_id' required.
 Action: Check the tool arguments against the exported schema and retry."
```

The `Action:` suffix is a reliable pattern: it's machine-readable enough that
agents can parse the instruction, and human-readable enough to be useful in logs.

Apply at both layers:
- **Tool descriptions**: explain what to do when the result is unexpected
- **Error responses**: include an `Action:` line whenever the error is recoverable

---

## Dark-Room Agent UX Testing

The highest-signal UX test: give the agent the server with no briefing,
ask it to complete a real task, then read the feedback queue.

**Protocol:**

1. Ensure `SubmitFeedback` is deployed and the system prompt includes the feedback directive
2. Give the agent a **real task** (not a toy: "find my unread messages from this week",
   "summarise what I was discussing with X yesterday")
3. No briefing — don't explain tools, names, or conventions
4. Instruction: *"As you work, use SubmitFeedback for anything surprising, confusing,
   or missing. At the end, submit a session summary: what felt intuitive, what was a
   WTF moment, what capability you wished existed."*
5. Let it run
6. Review `<server> feedback list` after the session

**Signals to look for:**

- **Confusing names** — agent tried to call a tool that doesn't exist because the name implied it should
- **Ambiguous descriptions** — agent passed wrong values or misread field semantics
- **Missing error recovery** — error with no `Action:` hint; agent stalled
- **Redundant round-trips** — agent called three tools to do what one should do
- **Reached-for capabilities** — clear signal for the next iteration
- **Contract violations** — agent expected one behaviour, got another

**When to run:** after any significant change to the tool surface — per change,
not per release. One session takes minutes; issues caught here cost far less
than issues discovered mid-task by real users.

---

## Post-MVP Tool Surface Normalization

After the first working version ships, do a dedicated tool surface review with agents —
not task-based, but explicitly about the API itself.

**Why:** the first version of a tool surface is shaped by how the developer thinks,
not how agents reason. Smart agents have distinct cognitive trajectories — they
form expectations from names, infer semantics from parameter structure, make
analogies to other tools. A surface that's technically correct can still be
cognitively dissonant.

**Protocol:**

1. Present the full tool catalogue to one or more capable agents (different models = different
   blind spots)
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

**What to optimise for:**

The goal is **cognitive congruence** — tool names, parameter names, and descriptions
should match the way a capable agent naturally thinks when solving problems in this domain.
A tool is well-named if an agent reaches for it without being told to. A parameter is
well-structured if filling it in feels like completing a thought, not consulting a spec.

**When to run:** once after the first complete tool surface. Then again after any
major redesign. This is a design review, not a QA step — run it before the surface
stabilises, not after.

---

## The SubmitFeedback + System Prompt Combination

The most effective pairing: the system prompt instructs agents to submit feedback
proactively, which turns every production session into a dark-room test automatically.

```
"Use SubmitFeedback immediately when a tool response is wrong,
 surprising, or missing a useful capability — don't wait until end of session."
```

The operator reviews the queue async, no ceremony required.
Over time the feedback queue is the primary UX signal for what to fix next.

For deeper analysis — correlating feedback with specific task types — pair with
`declare_session_task`: agent declares intent before work, all calls and feedback
are auto-correlated. → `feedback-tool.md §Session-Level Task Tracking`
