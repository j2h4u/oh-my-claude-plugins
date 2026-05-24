# Worked example — Tasks (SEP-1686) wire shape

> Load when implementing the spec-primitive long-running pattern. **Status today (2026-05):** no tracked client negotiates `tasks` at `initialize` and the major SDKs (`mcp`/FastMCP, `@modelcontextprotocol/sdk-typescript`) do not yet expose first-class registration helpers — wire shapes below may need to be hand-emitted in the capabilities/tool payload. Use the roll-your-own pattern (bottom of this file, also in [tool-design.md §Fallback](../references/tool-design.md#fallback--roll-your-own-async-handle)) as the default; verify SDK + [clients.md cross-client matrix](../references/clients.md#cross-client-capability-matrix) before shipping `taskSupport: required`.
>
> Decision context — when to reach for this vs. blocking vs. roll-your-own: [tool-design.md §Long-Running Operations](../references/tool-design.md#long-running-operations).

## 1. Declare the `tasks` capability at `initialize`

Without this the client will not augment any call:

```jsonc
{
  "capabilities": {
    "tools": {},
    "tasks": { "requests": { "tools/call": true } }
  }
}
```

## 2. Declare per-tool intent with `execution.taskSupport`

```jsonc
{
  "name": "deep_research",
  "description": "...",
  "execution": { "taskSupport": "optional" }  // "forbidden" | "optional" | "required"
}
```

`"optional"` is the only value safe to ship today: clients that don't negotiate `tasks` invoke the tool synchronously; clients that do negotiate it may augment. **Do not set `"required"` until the [clients.md matrix](../references/clients.md#cross-client-capability-matrix) confirms your target client negotiates `tasks` — `"required"` rejects synchronous calls and breaks the tool on every other client.**

| Value | Meaning |
|-------|---------|
| `forbidden` | Default. Tool is invoked synchronously; no task augmentation. |
| `optional` | Client may choose to augment with a task or call synchronously. |
| `required` | Client must augment with a task — synchronous call is rejected. |

## 3. Wire shape when the client augments

```jsonc
// Client → server
{"method":"tools/call","params":{"name":"deep_research","arguments":{...},"task":{"ttl":600000}}}
// Server → client (immediate)
{"result":{"taskId":"...","status":"working","createdAt":"...","ttl":600000,"pollInterval":2000}}
// Client polls
{"method":"tasks/get","params":{"taskId":"..."}}
// Terminal: working | input_required | completed | failed | cancelled
{"method":"tasks/result","params":{"taskId":"..."}}  // returns the original CallToolResult
{"method":"tasks/cancel","params":{"taskId":"..."}}  // optional
```

## Server-side invariants

- The receiver generates the task ID and may shorten the requested `ttl`.
- Clients poll. `notifications/tasks/status` is optional — requestors must not rely on it.
- Bind tasks to the session / auth context; use high-entropy IDs.

## Roll-your-own fallback (use today)

Two ordinary tools, no spec feature:

1. Submit tool returns immediately with a domain `id` and `status: "working"`.
2. A separate polling tool (`get_task_status`, `check_job_result`) takes the `id` and returns current state.
3. Final state returns the actual result or error.

Same invariant: the first tool never blocks; it only enqueues work and returns a handle. The pattern leaks polling cadence into prompt engineering and depends on the agent remembering to call the status tool — switch to the spec primitive above once your target clients support it.
