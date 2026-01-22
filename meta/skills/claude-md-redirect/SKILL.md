---
name: claude-md-redirect
description: This skill should be used when the user asks to "update CLAUDE.md", "edit CLAUDE.md", "write to CLAUDE.md", "create CLAUDE.md", "add to project memory", mentions "CLAUDE.md", or refers to project-specific notes and learnings. Redirects these operations to AGENTS.md instead, working with the PostToolUse hook that ensures @./AGENTS.md reference in CLAUDE.md for proper project context management.
user-invocable: false
---

# CLAUDE.md → AGENTS.md Redirect

**When asked to update, edit, or write to CLAUDE.md — use AGENTS.md instead.**

## Why

The project uses AGENTS.md for storing project-specific notes, learnings, and context. CLAUDE.md is reserved for the hook-managed reference.

## Hook Behavior

A PostToolUse hook (`~/.claude/hooks/ensure-agents-ref.sh`) automatically:
- Triggers after Write/Edit operations on CLAUDE.md
- Adds `@./AGENTS.md` reference at the beginning if not present

However, the hook doesn't always trigger (e.g., when CLAUDE.md doesn't exist yet). This skill ensures correct behavior regardless.

## Rules

1. **Never create or edit CLAUDE.md directly**
2. **Write all project notes to AGENTS.md**
3. **When user says "update CLAUDE.md"** — write to AGENTS.md instead
4. **Inform the user** that you're writing to AGENTS.md

## AGENTS.md Location

- Place AGENTS.md in the project root (same level as CLAUDE.md would be)
- Use relative path: `./AGENTS.md`
