#!/usr/bin/env bash
set -euo pipefail

# Хук для автоматического добавления @./AGENTS.md в CLAUDE.md
# Срабатывает после Write или Edit операций

# consts
declare -r AGENTS_REF='@./AGENTS.md'

# vars
declare input file_path tmp

# code
input=$( cat )
file_path=$( echo "$input" | jq --raw-output '.tool_input.file_path // empty' )

# assert: file path is present
[[ -n "$file_path" ]] || exit 0

# assert: file is CLAUDE.md (but not CLAUDE.local.md)
[[ "$file_path" == *'/CLAUDE.md' || "$file_path" == 'CLAUDE.md' ]] || exit 0

# assert: file exists
[[ -f "$file_path" ]] || exit 0

# assert: reference not already present
! grep --quiet --extended-regexp '@\.?/?AGENTS\.md' "$file_path" || exit 0

# add reference at the beginning
tmp=$( mktemp )
echo "$AGENTS_REF" > "$tmp"
echo '' >> "$tmp"
cat "$file_path" >> "$tmp"
mv "$tmp" "$file_path"

exit 0
