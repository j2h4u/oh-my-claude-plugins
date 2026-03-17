<!-- Source: https://code.claude.com/docs/en/sub-agents -->
# Subagents

> Create and use specialized AI subagents in Claude Code for task-specific workflows and improved context management.

Custom subagents in Claude Code are specialized AI assistants that can be invoked to handle specific types of tasks. They enable more efficient problem-solving by providing task-specific configurations with customized system prompts, tools and a separate context window.

**Benefits**:
- Preserve context by isolating exploration/implementation
- Enforce constraints via tool restrictions
- Reuse configs across projects
- Specialize behavior for domains
- Control costs (route to cheaper models like Haiku)

## Built-in Subagents

| Agent | Model | Tools | Purpose |
|-------|-------|-------|---------|
| **Explore** | Haiku | Read-only | Fast codebase search/analysis |
| **Plan** | Inherit | Read-only | Research before planning |
| **General-purpose** | Inherit | All | Complex multi-step tasks |
| **Other** | Various | Task-specific | Bash, statusline, Claude Code Guide |

## Quick Start: Create Subagent

1. Run `/agents` in Claude Code
2. Select **Create new agent** → **User-level** (saves to `~/.claude/agents/`)
3. Select **Generate with Claude** and describe agent purpose
4. Choose tools (e.g., read-only for reviewers)
5. Select model (e.g., Sonnet for code analysis)
6. Pick color and save

**Scopes & Priority** (highest to lowest):
1. `--agents` CLI flag (session-only)
2. `.claude/agents/` (project)
3. `~/.claude/agents/` (user)
4. Plugin's `agents/` directory

## Subagent File Format

```markdown
---
name: unique-id
description: When Claude should use this
tools: Read, Grep, Glob
model: sonnet
---

System prompt text here.
```

**Required fields**: `name`, `description`

**Optional fields**:

| Field | Purpose |
|-------|---------|
| `tools` | Allowlist tools (inherits all if omitted) |
| `disallowedTools` | Denylist tools |
| `model` | `sonnet`, `opus`, `haiku`, or `inherit` (default) |
| `permissionMode` | `default`, `acceptEdits`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | Max agentic turns |
| `skills` | Inject skill content at startup |
| `mcpServers` | MCP servers for subagent |
| `hooks` | Lifecycle hooks (`PreToolUse`, `PostToolUse`, `Stop`) |
| `memory` | Persistent memory scope: `user`, `project`, `local` |
| `background` | Run as background task (default: false) |
| `isolation` | `worktree` for isolated git worktree |

## Tool Control

**Restrict tools**:
```yaml
tools: Read, Grep, Glob, Bash
disallowedTools: Write, Edit
```

**Control spawned subagents**:
```yaml
tools: Agent(worker, researcher), Read, Bash
```

**Permission modes**: `default` (prompts), `acceptEdits` (auto-accept), `dontAsk` (auto-deny), `bypassPermissions` (skip checks)

## Conditional Rules with Hooks

Use `PreToolUse` hooks to validate operations:

```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-readonly-query.sh"
```

Hook receives JSON via stdin; exit code 2 blocks operation.

## Persistent Memory

Enable knowledge retention across sessions:
```yaml
memory: user  # or 'project' or 'local'
```

- `user`: `~/.claude/agent-memory/<agent-name>/` (all projects)
- `project`: `.claude/agent-memory/<agent-name>/` (team shareable)
- `local`: `.claude/agent-memory-local/<agent-name>/` (not in VCS)

Subagent reads/writes `MEMORY.md` (first 200 lines in prompt).

## Working with Subagents

**Automatic delegation**: Based on subagent `description` field. Request explicitly: "Use the test-runner agent..."

**Foreground vs Background**:
- Foreground: blocks until complete, interactive prompts
- Background: concurrent, pre-approves permissions (press Ctrl+B to background)

**Resume subagents**: Retain full history; continue previous work:
```
Use code-reviewer to review auth module
[completes]
Continue that review for authorization logic
[resumes with prior context]
```

**Transcripts**: Stored at `~/.claude/projects/{project}/{sessionId}/subagents/agent-{agentId}.jsonl`

## Patterns

**Isolate high-volume ops**: Run tests, fetch docs, process logs in subagent to keep verbose output out of main conversation.

**Parallel research**: Spawn multiple subagents for independent investigations.

**Chain subagents**: Multi-step workflows with sequential delegation.

**Main conversation vs subagents**:
- Main: frequent iteration, shared context, quick changes, low latency
- Subagents: verbose output, tool restrictions, self-contained work

## Example Subagents

**Code Reviewer** (read-only): `tools: Read, Grep, Glob, Bash` — reviews without modifying

**Debugger** (can fix): `tools: Read, Edit, Bash, Grep, Glob` — diagnoses and fixes issues

**Data Scientist**: `model: sonnet` — SQL/BigQuery analysis with specialized prompt

**DB Query Validator**: `tools: Bash` + `PreToolUse` hook to block write SQL operations

## Next Steps

- Distribute subagents with plugins
- Run Claude Code programmatically (Agent SDK)
- Use MCP servers for external tools
