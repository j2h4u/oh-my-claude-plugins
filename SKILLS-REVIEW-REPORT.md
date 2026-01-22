# Skills Review Report

**Generated:** 2026-01-23
**Skills Reviewed:** 19
**Review Agent:** plugin-dev:skill-reviewer

## Executive Summary

### Overall Ratings Distribution

| Rating | Count | Skills |
|--------|-------|--------|
| **Pass (High Quality)** | 4 | gh, mcp-builder, vercel-react-best-practices, doc-coauthoring |
| **Needs Minor Improvement** | 1 | cli-skill-creator |
| **Needs Improvement** | 11 | dignified-bash, dignified-python, git-workflow-manager, claude-md-redirect, opencode-config, changelog-generator, linux-sysadmin, claude-md-writer, meeting-insights-analyzer, readme-generator, kaizen |
| **Needs Major Revision** | 3 | web-artifacts-builder, software-architecture, web-design-guidelines |

### Common Issues Across All Skills

1. **Description Format Problems (15/19 skills)** - Most critical issue
   - Missing "This skill should be used when..." third-person format
   - Insufficient trigger phrases
   - Missing specific user queries

2. **Missing Progressive Disclosure (8/19 skills)**
   - No examples/ directories
   - No references/ directories
   - Content that could be better organized

3. **Word Count Issues (3/19 skills)**
   - Too short: web-design-guidelines (176 words)
   - Slightly high: cli-skill-creator (2,776 words)
   - Appropriate range: Most others (1,000-3,000 words)

---

## Critical Issues (Must Fix)

### 1. Description Format - 15 Skills Affected

**Skills with Critical Description Issues:**
- dignified-bash
- dignified-python
- git-workflow-manager
- web-artifacts-builder
- claude-md-redirect
- opencode-config
- changelog-generator
- linux-sysadmin
- claude-md-writer
- meeting-insights-analyzer
- readme-generator
- software-architecture
- kaizen
- web-design-guidelines
- cli-skill-creator

**Problem:** Descriptions don't follow best practices:
- Using imperative form ("Use when...") instead of third person ("This skill should be used when...")
- Missing specific trigger phrases users would say
- Too generic or too brief

**Impact:** Skills won't trigger properly when users need them.

**Solution Template:**
```yaml
description: This skill should be used when the user asks to "specific phrase 1", "specific phrase 2", "specific phrase 3", mentions "key concept", or needs [description of use case]. [Brief explanation of what it provides].
```

---

## Major Issues by Skill

### web-artifacts-builder (Needs Major Revision)

**Critical Issues:**
- Description lacks trigger phrases
- Missing references/ directory entirely
- Missing examples/ directory entirely
- Word count too low (446 words) - needs 800-1,200

**Major Issues:**
- No troubleshooting guide
- No component patterns reference
- Missing working examples

**Recommended Action:**
1. Rewrite description with specific triggers
2. Create references/troubleshooting.md
3. Create references/component-patterns.md
4. Create examples/ with 2 complete working examples
5. Expand SKILL.md to 800-1,200 words

---

### software-architecture (Needs Major Revision)

**Critical Issues:**
- Description FAR too broad: "in any case that relates to software development"
- Will trigger inappropriately for almost any coding task
- Missing key concept triggers (Clean Architecture, DDD, library-first)

**Major Issues:**
- Missing trigger phrases for specific concepts
- No supporting files despite content that needs examples
- No code examples (would benefit from before/after patterns)

**Recommended Action:**
1. **URGENT:** Completely rewrite description to be specific:
   - Add: "clean architecture", "domain driven design", "DDD"
   - Add: "library vs custom code", "avoid utils/helpers"
   - Remove: "in any case that relates to software development"
2. Create examples/ with good vs bad code patterns
3. Create references/library-recommendations.md

---

### web-design-guidelines (Needs Major Revision)

**Critical Issues:**
- Extremely brief (176 words vs 1,000-3,000 recommended)
- External dependency without fallback (WebFetch to GitHub)
- No examples showing what output looks like
- Incomplete workflow guidance

**Major Issues:**
- No error handling if external fetch fails
- Missing context about what Web Interface Guidelines are
- No examples of violations or fixes

**Recommended Action:**
1. Expand SKILL.md to 1,500+ words with context
2. Create examples/sample-review-output.md
3. Create references/guidelines-overview.md
4. Add error handling workflow

---

## Skills Requiring Description Fixes

### Priority 1: Critical Description Problems

#### changelog-generator
**Current:** Describes what it does, not when to use it
**Missing:** "create a changelog", "generate release notes", "write changelog"
**Fix:** Add specific user trigger phrases

#### claude-md-writer
**Current:** "Use when creating or refactoring CLAUDE.md"
**Missing:** "my CLAUDE.md is too big", "split large CLAUDE.md", "3-tier documentation"
**Fix:** Add pain point triggers and specific scenarios

#### meeting-insights-analyzer
**Current:** No trigger phrases in description
**Missing:** "analyze meeting transcripts", "review my communication patterns"
**Fix:** Add 8+ specific trigger phrases

#### git-workflow-manager
**Current:** "Use when committing, releasing..." (imperative)
**Missing:** "create a release", "bump version", "conventional commits"
**Fix:** Third-person format with specific triggers

#### linux-sysadmin
**Current:** Too brief, "system-level tasks" too vague
**Missing:** "configure cron jobs", "set up systemd services", "edit sudoers"
**Fix:** Add specific technical triggers

#### opencode-config
**Current:** Uses imperative "Use when"
**Missing:** "configure OpenCode", "change OpenCode model", "setup Z.AI"
**Fix:** Third-person with tool-specific triggers

#### readme-generator
**Current:** "Use when creating or rewriting README.md"
**Missing:** "generate README", "improve README", "document project"
**Fix:** Add more action verbs users would say

#### kaizen
**Current:** Grammar errors ("tehniquest", "architecturing"), not third person
**Missing:** "avoid over-engineering", "apply kaizen", "use YAGNI"
**Fix:** Fix typos and add principle-specific triggers

---

## Skills with Good Descriptions (Reference Examples)

### gh (Pass - High Quality)
**Excellent description:**
```yaml
description: This skill should be used when working with GitHub CLI (gh) for pull requests, issues, releases, and GitHub automation. Use when users mention gh commands, GitHub workflows, PR operations, issue management, or GitHub API access. Essential for understanding gh's mental model, command structure, and integration with git workflows.
```

**Why it works:**
- Third person format
- Specific trigger phrases ("gh commands", "PR operations")
- Clear scope
- Natural language users would actually say

### mcp-builder (Pass - High Quality)
**Good description (could be enhanced):**
```yaml
description: Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools. Use when building MCP servers to integrate external APIs or services, whether in Python (FastMCP) or Node/TypeScript (MCP SDK).
```

**Suggested enhancement:**
Add quoted trigger phrases: "create an MCP server", "build MCP integration", "use FastMCP"

---

## Progressive Disclosure Assessment

### Exemplary Implementation

**gh** - Perfect progressive disclosure:
- SKILL.md: 1,935 words (lean core)
- references/: 4 files, 15,518 words (detailed content)
- Clear loading strategy with grep patterns
- Word counts provided for context

**vercel-react-best-practices** - Textbook example:
- SKILL.md: 712 words (overview)
- rules/: 47 files, ~8,016 words (individual rules)
- AGENTS.md: 7,959 words (comprehensive reference)
- Perfect three-tier structure

**mcp-builder** - Excellent organization:
- SKILL.md: 1,792 words (workflow)
- reference/: 4 comprehensive guides
- scripts/: Working evaluation harness
- Clear separation of concerns

### Needs Improvement

**web-artifacts-builder** - Missing entirely:
- No references/ directory
- No examples/ directory
- All content crammed in 446-word SKILL.md

**software-architecture** - Underutilized:
- Only SKILL.md (509 words)
- Could benefit from examples/ with code samples
- Could use references/ for Clean Architecture deep dive

**web-design-guidelines** - Critically lacking:
- No examples/ showing sample output
- No references/ with guidelines overview
- Depends entirely on external WebFetch

---

## Word Count Analysis

| Skill | Words | Status | Recommendation |
|-------|-------|--------|----------------|
| web-design-guidelines | 176 | Too Short | Expand to 1,500+ |
| software-architecture | 509 | Acceptable | Could expand to 800-1,200 |
| readme-generator | 748 | Good | No change needed |
| vercel-react-best-practices | 712 | Good | No change needed |
| dignified-bash | 1,107 | Excellent | No change needed |
| git-workflow-manager | 464 | Good | No change needed |
| web-artifacts-builder | 446 | Too Lean | Expand to 800-1,200 |
| cli-skill-creator | 2,776 | High but OK | Could trim 200-400 words |
| mcp-builder | 1,792 | Excellent | No change needed |
| gh | 1,935 | Excellent | No change needed |

---

## Recommended Action Plan

### Phase 1: Critical Fixes (Highest Impact)

**Week 1 - Description Rewrites (15 skills)**

Priority order:
1. **software-architecture** - Current description will cause inappropriate triggering
2. **changelog-generator** - Won't trigger for "create changelog" requests
3. **claude-md-writer** - Won't trigger for "CLAUDE.md too big" pain point
4. **meeting-insights-analyzer** - No trigger phrases at all
5. **git-workflow-manager** - Wrong format
6. **kaizen** - Has typos ("tehniquest")
7. **linux-sysadmin** - Too generic
8. **opencode-config** - Imperative format
9. **readme-generator** - Missing key triggers
10. **web-artifacts-builder** - No triggers
11. **claude-md-redirect** - Not third person
12. **dignified-bash** - Awkward trigger format
13. **dignified-python** - Needs "This skill should be used when..."
14. **web-design-guidelines** - Missing triggers
15. **cli-skill-creator** - Minor enhancement

**Estimated Time:** 2-3 hours (15 minutes per skill)

### Phase 2: Major Structural Improvements

**Week 2 - Add Missing Directories**

1. **web-artifacts-builder** (Critical)
   - Create references/troubleshooting.md
   - Create references/component-patterns.md
   - Create examples/ with 2 working examples
   - Expand SKILL.md to 800-1,200 words

2. **web-design-guidelines** (Critical)
   - Expand SKILL.md to 1,500+ words
   - Create examples/sample-review-output.md
   - Create references/guidelines-overview.md

3. **software-architecture** (High)
   - Create examples/ with good vs bad patterns
   - Create references/library-recommendations.md

4. **linux-sysadmin** (Medium)
   - Create examples/ with docker-dns-watchdog.sh
   - Create examples/systemd/ with working timer

**Estimated Time:** 8-12 hours

### Phase 3: Enhancements

**Week 3 - Optional Improvements**

1. Add examples/ to skills that would benefit:
   - changelog-generator
   - meeting-insights-analyzer
   - opencode-config

2. Trim slightly verbose skills:
   - cli-skill-creator (reduce from 2,776 to ~2,400 words)

**Estimated Time:** 4-6 hours

---

## Quick Wins (< 15 minutes each)

These can be done immediately for quick improvements:

1. **kaizen** - Fix typo "tehniquest" → "techniques" (Line 3)
2. **git-workflow-manager** - Update example date from 2025 to 2026 (Line 112)
3. **mcp-builder** - Fix section numbering 1.3→1.2, 1.4→1.3 (Line 56)
4. **dignified-bash** - Remove deprecated `user-invocable: false` field
5. **dignified-python** - Remove personal reference "erk's dignified Python standards"

---

## Skills Ready for Production

These 4 skills are high quality and require minimal changes:

### 1. gh (Pass - High Quality)
- Excellent progressive disclosure
- Strong description
- Comprehensive coverage
- Minor: Could add more command triggers ("gh pr create", "gh issue list")

### 2. mcp-builder (Pass - High Quality)
- Exemplary structure
- Working evaluation tools included
- Minor: Fix section numbering, enhance description

### 3. vercel-react-best-practices (Pass - Exemplary)
- Textbook progressive disclosure
- 47 rule files + comprehensive AGENTS.md
- Minor: Verify file path references

### 4. doc-coauthoring (Pass)
- Well-structured workflow
- Good word count (2,466)
- Minor: Consolidate redundant trigger clauses in description

---

## Summary Statistics

- **Total Skills:** 19
- **Pass (Production Ready):** 4 (21%)
- **Needs Minor Fixes:** 1 (5%)
- **Needs Improvement:** 11 (58%)
- **Needs Major Revision:** 3 (16%)

**Most Common Issue:** Description format (15/19 = 79%)
**Estimated Fix Time:** 20-30 hours total
**Quick Wins Available:** 5 skills (< 15 min each)

---

## Detailed Issue Breakdown

### By Priority

**Critical (Must Fix):**
- 15 description format issues
- 3 skills with insufficient content (web-design-guidelines, web-artifacts-builder, software-architecture)

**Major (Should Fix):**
- 8 skills missing progressive disclosure directories
- 3 skills with structural organization issues

**Minor (Nice to Have):**
- 5 typos/formatting issues
- 2 skills slightly over/under word count targets
- Various small enhancements

---

## Files by Category

### Excellent Structure (Use as Templates)
- `git/skills/gh/` - Progressive disclosure master class
- `web/skills/vercel-react-best-practices/` - Three-tier reference system
- `meta/skills/mcp-builder/` - Working tools + references
- `docs/skills/doc-coauthoring/` - Clear workflow structure

### Needs Major Work
- `web/skills/web-artifacts-builder/` - Add 4+ files, expand content
- `coding-standards/skills/software-architecture/` - Complete rewrite needed
- `web/skills/web-design-guidelines/` - Expand from 176 to 1,500+ words

### Quick Fix Candidates
- `coding-standards/skills/kaizen/` - Fix typos only
- `git/skills/git-workflow-manager/` - Update date example
- `meta/skills/mcp-builder/` - Renumber sections

---

## Next Steps

1. **Immediate (Today):**
   - Fix 5 quick wins (typos, dates, numbering)
   - Start description rewrites for top 5 critical skills

2. **This Week:**
   - Complete all 15 description rewrites
   - Begin structural improvements for web-artifacts-builder

3. **Next Week:**
   - Add missing directories and examples
   - Expand web-design-guidelines content

4. **Following Week:**
   - Optional enhancements
   - Final validation pass

---

**Report End**
