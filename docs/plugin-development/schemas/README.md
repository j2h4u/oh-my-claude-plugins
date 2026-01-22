# Plugin Development Schemas

JSON Schema definitions for validating Claude Code plugin files.

## Available Schemas

### `hooks.schema.json`

**Purpose**: Validates plugin `hooks/hooks.json` files

**Based on**: Official Claude Code settings schema from [schemastore.org](https://json.schemastore.org/claude-code-settings.json)

**Usage**:
```bash
# Validate all hooks.json files in repository
python3 validate-hooks.py

# Or use with any JSON schema validator
jsonschema -i ../../meta/hooks/hooks.json hooks.schema.json
```

**Structure**:
```json
{
  "description": "Optional description",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/hook.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Supported hook events**:
- `PreToolUse` - Before tool execution
- `PostToolUse` - After tool execution
- `UserPromptSubmit` - When user submits prompt
- `Notification` - On notifications
- `Stop` - When agent stops
- `SubagentStop` - When subagent stops
- `SessionStart` - Session initialization
- `SessionEnd` - Session termination
- `PreCompact` - Before context compaction

**Hook types**:
- `command` - Bash command execution
- `prompt` - LLM prompt evaluation (advanced)

## CI/CD Integration

The `validate-hooks.py` script runs automatically in GitHub Actions on every push and PR.

**Workflow job**: `validate-hooks-schema` in `.github/workflows/validate-plugins.yml`

## Adding New Schemas

When adding new schemas:

1. Create `<name>.schema.json` following JSON Schema Draft 7
2. Add validation script `validate-<name>.py`
3. Add CI/CD job in `.github/workflows/validate-plugins.yml`
4. Document in this README

## IDE Autocomplete

For better autocomplete in your IDE (including 50+ environment variables), you can use the community-maintained improved schema:

```json
{
  "$schema": "https://assets.turboai.dev/claude-code-settings.improved.json"
}
```

Add this to your `.claude/settings.json` or `.claude/settings.local.json` for enhanced IntelliSense in VSCode and other editors.

**Note**: This is an unofficial community schema with richer autocomplete support. For CI/CD validation, we use the official schema from schemastore.org.

## References

- [JSON Schema specification](https://json-schema.org/draft-07/schema)
- [Official Claude Code settings schema](https://json.schemastore.org/claude-code-settings.json) (used in CI/CD)
- [Community improved schema](https://assets.turboai.dev/claude-code-settings.improved.json) (for IDE autocomplete)
- [Claude Code hooks documentation](../../hooks.md)
- [Plugin development guide](../../plugins.md)
