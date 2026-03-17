<!-- Source: https://code.claude.com/docs/en/slash-commands -->
# Slash commands

> Control Claude's behavior during an interactive session with slash commands.

## Built-in slash commands

| Command | Description |
|---------|-------------|
| `/bug` | Report bugs (sends conversation to Anthropic) |
| `/clear` | Clear conversation history |
| `/compact [instructions]` | Compact conversation, with optional focus instructions |
| `/config` | Open settings configuration |
| `/cost` | Show token usage statistics |
| `/doctor` | Checks the health of your Claude Code installation |
| `/help` | Get usage help |
| `/init` | Initialize project with CLAUDE.md guide |
| `/login` | Switch Anthropic accounts |
| `/logout` | Sign out from your Anthropic account |
| `/memory` | Edit CLAUDE.md memory files |
| `/model` | Select or change AI model |
| `/permissions` | View or update permissions |
| `/plugin` | Manage plugins |
| `/pr-review` | Review a pull request |
| `/review` | Review code changes |
| `/status` | View account and system status |
| `/terminal-setup` | Install Shift+Enter key binding for newlines |
| `/vim` | Enter vim mode for multi-line editing |

## Custom slash commands (Skills)

Create custom commands by adding Skills:

- **Personal**: `~/.claude/skills/<skill-name>/SKILL.md`
- **Project**: `.claude/skills/<skill-name>/SKILL.md`
- **Plugin**: `<plugin>/skills/<skill-name>/SKILL.md`

See [Skills](/en/skills) for full details on creating custom slash commands.
