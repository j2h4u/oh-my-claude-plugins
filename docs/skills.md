<!-- Source: https://code.claude.com/docs/en/skills -->
# Agent Skills

> Create, manage, and share Skills to extend Claude's capabilities in Claude Code.

Skills extend Claude's capabilities. Create `SKILL.md` with instructions; Claude adds to toolkit. Invoke with `/skill-name` or let Claude load automatically.

**Key locations:**
- Enterprise: Managed settings
- Personal: `~/.claude/skills/<skill-name>/SKILL.md`
- Project: `.claude/skills/<skill-name>/SKILL.md`
- Plugin: `<plugin>/skills/<skill-name>/SKILL.md`

Priority: enterprise > personal > project

## Bundled Skills

- **`/simplify`**: Reviews files for reuse, quality, efficiency; spawns 3 parallel agents
- **`/batch <instruction>`**: Large-scale changes across codebase in parallel; 5-30 independent units
- **`/debug [description]`**: Troubleshoots session via debug log
- **`/loop [interval] <prompt>`**: Runs prompt repeatedly on schedule
- **`/claude-api`**: Loads Claude API reference (Python, TypeScript, Java, Go, Ruby, C#, PHP, cURL)

## Create a Skill

**Structure:**
```
skill-name/
├── SKILL.md (required)
├── template.md (optional)
├── examples/ (optional)
└── scripts/ (optional)
```

**SKILL.md format:**
```yaml
---
name: skill-name
description: When to use this skill
disable-model-invocation: true  # optional: manual only
user-invocable: false           # optional: Claude only
allowed-tools: Read, Grep       # optional: restrict tools
context: fork                   # optional: run in subagent
agent: Explore                  # optional: agent type
---
Instructions here...
```

## Frontmatter Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | No | Display name (lowercase, hyphens, max 64 chars); defaults to directory name |
| `description` | Recommended | When/why to use; Claude uses for auto-load decision |
| `argument-hint` | No | Autocomplete hint, e.g., `[issue-number]` |
| `disable-model-invocation` | No | `true` = manual only (default: false) |
| `user-invocable` | No | `false` = Claude only (default: true) |
| `allowed-tools` | No | Comma-separated list of accessible tools |
| `model` | No | Model to use when skill active |
| `context` | No | `fork` = run in isolated subagent |
| `agent` | No | Subagent type (Explore, Plan, general-purpose) |
| `hooks` | No | Lifecycle hooks |

## String Substitutions

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments passed |
| `$ARGUMENTS[N]` / `$N` | Specific argument by index |
| `${CLAUDE_SESSION_ID}` | Current session ID |
| `${CLAUDE_SKILL_DIR}` | Skill directory path |

**Example:**
```yaml
---
name: fix-issue
description: Fix GitHub issue
---
Fix issue $ARGUMENTS per coding standards
```
Running `/fix-issue 123` replaces `$ARGUMENTS` with `123`.

## Skill Types

**Reference content:** Conventions, patterns, style guides (runs inline)
**Task content:** Step-by-step instructions for specific actions (often `disable-model-invocation: true`)

## Invocation Control

| Config | You invoke | Claude invokes | Context loading |
|--------|-----------|----------------|-----------------|
| Default | ✓ | ✓ | Description always; full skill on invoke |
| `disable-model-invocation: true` | ✓ | ✗ | Description not in context; full skill on your invoke |
| `user-invocable: false` | ✗ | ✓ | Description always; full skill on invoke |

## Advanced Patterns

**Dynamic context with shell commands:**
```yaml
---
name: pr-summary
---
PR diff: !`gh pr diff`
PR comments: !`gh pr view --comments`
```
Commands execute before Claude sees prompt; output replaces placeholder.

**Run in subagent:**
```yaml
---
name: deep-research
context: fork
agent: Explore
---
Research $ARGUMENTS thoroughly...
```

**Restrict tool access:**
```yaml
---
name: safe-reader
allowed-tools: Read, Grep, Glob
---
```

## Nested Discovery

Skills in nested `.claude/skills/` directories auto-discovered (monorepo support). Skills from `--add-dir` auto-loaded with live change detection.

## Permission Rules

Control skill access via `/permissions`:
```
Skill(commit)              # Allow specific skill
Skill(deploy *)            # Allow prefix match
Skill                      # Deny all skills
```

## Share Skills

- **Project**: Commit to `.claude/skills/` in version control
- **Plugin**: Create `skills/` directory in plugin
- **Managed**: Deploy organization-wide via managed settings

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Skill not triggering | Check description keywords; verify in skill list; invoke directly with `/name` |
| Triggers too often | Make description more specific; add `disable-model-invocation: true` |
| Many skills not seen | Budget limit ~2% context window (16KB fallback); override with `SLASH_COMMAND_TOOL_CHAR_BUDGET` env var |

## Related Resources

- Subagents, Plugins, Hooks, Memory, Interactive mode, Permissions
