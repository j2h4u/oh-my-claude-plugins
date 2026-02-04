---
name: dignified-bash
description: This skill should be used when the user asks to "write bash script", "create shell script", "review bash code", "write hook", "create systemd service script", "fix shellcheck warnings", "improve bash script", mentions "bash", "shell", ".sh files", or works with any shell scripting including hooks and CLI tools. Enforces bash purist style with strict mode, die() function, proper variable declarations, assertion comments, result comments, shellcheck compliance, and structured function layout.
allowed-tools: Bash
---

# Bash Coding Style Guide

## Before You Write Bash: Choose the Right Tool

**First, evaluate whether Bash is the right choice for the task.** Bash excels at:
- System automation, glue scripts, pipelines
- File operations, process management, environment setup
- Hooks, init scripts, simple CLI wrappers
- Tasks where external tools (`grep`, `awk`, `sed`, `curl`) do the heavy lifting

**Consider Python instead when the task involves:**
- Complex JSON/YAML parsing and transformation (not just `jq` one-liners)
- Data structures: nested objects, lists of dicts, complex state
- Error handling with structured exceptions
- HTTP APIs with authentication, retries, error handling
- String manipulation beyond simple patterns
- Anything requiring classes, types, or testability

Python is available on virtually every Linux system out of the box. Switching from Bash+jq to Python often **reduces code size by 2-3x** while improving readability and maintainability.

**Rule of thumb:** If your Bash script has more `jq` calls than shell commands, or exceeds ~100 lines, reconsider the language choice.

---

**IMPORTANT: Always use Bash, never plain sh.** Even for simple scripts, hooks, or one-liners — always use `#!/usr/bin/env bash`. Plain POSIX sh lacks essential features (arrays, `[[ ]]`, `set -o pipefail`) and there's no benefit to avoiding bash on modern systems.

All shell scripts must adhere to the **Bash Purist** style to ensure robustness, readability, and maintainability.

### 1. Shebang & Strict Mode
- **Shebang**: Always use the portable form:
  ```bash
  #!/usr/bin/env bash
  ```
- **Fail Fast**: Always start scripts with strict mode:
  ```bash
  set -euo pipefail
  ```

### 2. Verification & Linting
- **ShellCheck**: All scripts MUST pass `shellcheck` without warnings.
  - If `shellcheck` is not available, install it first: `sudo apt install shellcheck` (Debian/Ubuntu) or equivalent for other systems.
  - Always run `shellcheck <script.sh>` after writing or modifying a script.

### 3. The die() Function
- Always define a `die()` function for fatal errors instead of inline `{ echo "error"; exit 1; }`:
  ```bash
  function die {
      local -r message="${1:-}"
      local -ri code="${2:-1}"

      echo "FATAL: ${message}"
      exit "$code"
  } 1>&2
  ```
- **Note:** Redirect stderr at function level with `} 1>&2` instead of `>&2` inside the function. This makes all function output go to stderr automatically.
- Usage:
  ```bash
  # assert: config file exists
  [[ -f "$config_file" ]] || die "Config file not found: $config_file"

  # assert: source library exists
  source "$lib_path" || die "Failed to source: $lib_path" 2
  ```
- **Pattern for logging functions:** Use the same `} 1>&2` pattern for any function that should output to stderr:
  ```bash
  function log_error {
      local -r message="$1"
      echo "ERROR: ${message}"
  } 1>&2

  function log_warn {
      local -r message="$1"
      echo "WARN: ${message}"
  } 1>&2
  ```

### 4. Variables & Constants
- **Naming Convention**:
  - `UPPER_CASE`: Read-only constants (`declare -r`) and environment variables.
  - `lower_case`: Local variables and function arguments.
- **Declarations**:
  - Always use `declare`, `local`, or `readonly`.
  - Use `declare -i` or `local -i` for integers (e.g., boolean flags 0/1, counters).
  - Use `declare -r` or `local -r` for immutable variables.
  - Use `local -a` for indexed arrays inside functions.
  - Use `local -A` for associative arrays (dicts) inside functions.
  - **Multiple declarations**: When declaring multiple variables of the same type, put them on one line. If declaring more than 2-3 variables, group them by domain/purpose on separate lines:
    ```bash
    # few variables: single line
    local network_mode container_name

    # many variables: group by domain
    local project project_dir project_config
    local container_name container_id
    local output result
    ```
- **Assignment**:
  - Separate declaration and assignment for command substitutions to prevent masking return codes (fixes `SC2155`):
    ```bash
    local result
    result=$( some_command )
    ```
  - Use `$( <file )` instead of `$(cat file)` to read file contents (avoids subprocess):
    ```bash
    content=$( <"$file_path" )
    ```

### 5. Subshell Awareness

Command substitution `$(...)` creates a **subshell** where:
- stdin is not inherited from parent
- variable changes are not visible to parent

Be careful with functions that read stdin or modify parent scope — calling them via `$(func)` will fail silently:
```bash
# BROKEN: subshell doesn't get stdin
input=$( read_stdin_func )
```

**Solution**: Use **nameref** (`local -n`) to assign directly to caller's variable:
```bash
function read_stdin {
    local -n ref="$1"
    IFS= read -r -d '' ref || true
}

read_stdin 'my_data'  # pass variable NAME, not value
```

### 6. Associative Arrays (Dicts)
- Use associative arrays (`declare -A` / `local -A`) where they simplify code logic or improve readability.
- Good use cases: tracking state, caching lookups, grouping related data.
- Don't use them just for the sake of it — only when they provide a clear benefit.
- Multi-element initialization must be on separate lines, with quoted keys and values:
  ```bash
  # dicts
  local -A config=(
      ['host']='localhost'
      ['port']='8080'
      ['timeout']='30'
  )

  # dicts: incremental assignment
  declare -A restarted_projects
  restarted_projects['myproject']=1
  ```

### 7. Arithmetic Context
- Use arithmetic contexts `(( ))` for integer comparisons and boolean checks.
- **Spacing**: Add spaces inside parentheses for readability:
  ```bash
  # flags
  declare -i is_dry_run=0

  if (( is_dry_run )); then
      ...
  fi

  (( count++ ))
  (( total = a + b ))
  ```

### 8. Conditionals
- Always use double brackets `[[ ]]` for conditional expressions instead of the legacy `[` (test) command.
- **Combine conditions** inside single brackets using `&&` and `||`:
  ```bash
  # good: single bracket with combined conditions
  if [[ -n "$project" && -n "$project_dir" ]]; then
      ...
  fi

  # avoid: multiple brackets
  if [[ -n "$project" ]] && [[ -n "$project_dir" ]]; then
      ...
  fi
  ```
- **Spacing**: Add spaces inside brackets and parentheses:
  ```bash
  [[ -d "$dir" ]]
  (( count > 0 ))
  result=$( some_command )
  ```
- **Pitfall: `&&`/`||` chains are NOT if-then-else.** The pattern `foo && bar || baz` does NOT work like `if foo; then bar; else baz; fi`. If `bar` returns non-zero, `baz` will also execute:
  ```bash
  # BROKEN: baz runs if bar fails, not just if foo fails
  check_something && do_work || handle_error

  # SAFE: bar cannot fail (variable assignment)
  [[ -f "$file" ]] && found=1 || found=0

  # CORRECT: use proper if-then-else for complex logic
  if check_something; then
      do_work
  else
      handle_error
  fi
  ```
  Only use `&&`/`||` chains when the middle command cannot fail (e.g., variable assignments, `echo`, `true`).
- **Pitfall: `read` in loops and last line without newline.** `read` returns non-zero at EOF even if it read data. If the last line has no trailing newline, it will be skipped:
  ```bash
  # BROKEN: skips last line if file has no trailing newline
  while read -r line; do
      process "$line"
  done < file

  # CORRECT: also check if variable has content
  while read -r line || [[ -n "$line" ]]; do
      process "$line"
  done < file
  ```

### 9. Assertions & Early Returns
- **Avoid nested ifs and ladders** — they are hard to read. Use early returns instead.
- **All assertions must have a comment** in the format `# assert: <description>`:
  ```bash
  # good: early returns with assert comments
  function process_file {
      local -r file="$1"

      # assert: file exists
      [[ -f "$file" ]] || return 1

      # assert: file is readable
      [[ -r "$file" ]] || return 1

      # main logic here, not nested
      ...
  }
  ```
- **Fatal assertions** (script must exit):
  ```bash
  # assert: config file exists
  [[ -f "$config_file" ]] || die "Config not found: $config_file"
  ```
- **Non-fatal assertions** (function returns):
  ```bash
  # assert: directory exists
  [[ -d "$target_dir" ]] || return 1

  # assert: DNS is broken (inverted logic)
  check_dns "$container" || return 0
  ```

### 10. Implicit Return Code
- When a function's return code is determined by its last command, this is valid and concise.
- **Always precede with a comment** in the format `# result: <description>`:
  ```bash
  function check_container_dns {
      # args
      local -r container_id="$1"

      # vars
      local resolv_conf

      # code
      resolv_conf=$( docker exec "$container_id" cat /etc/resolv.conf 2>/dev/null ) || return 1

      # result: true if DNS is broken
      [[ "$resolv_conf" == *"$DNS_ERROR_PATTERN"* ]]
  }

  function is_valid_port {
      # args
      local -r port="$1"

      # result: true if port is in valid range
      (( port >= 1 && port <= 65535 ))
  }
  ```

### 11. Functions Structure
Functions must follow a strict "Sections" layout:
1.  **# args**: explicit parsing of arguments into `local -r` variables.
2.  **# vars**: declaration of local variables, grouped by type with comments:
    - `# consts` for `local -r`
    - `# flags` for `local -i` boolean flags (0/1)
    - `# arrays` for `local -a`
    - `# dicts` for `local -A`
    - Plain `local` for regular variables
3.  **# code**: the actual logic.

**Example**:
```bash
function process_data {
    # args
    local -r input_dir="$1" output_file="$2"

    # consts
    local -r max_items=100

    # flags
    local -i verbose=0

    # arrays
    local -a items

    # dicts
    local -A item_counts

    # vars
    local -i count=0
    local item

    # code
    # assert: input directory exists
    [[ -d "$input_dir" ]] || return 1

    for item in "${input_dir}"/*; do
        ...
    done
}
```

### 12. External Dependencies
- Explicitly pass global state (like configuration paths) as arguments to functions. Avoid hidden dependencies on global variables inside helper functions.
- Use `die()` for failed source:
  ```bash
  source "$script_dir/lib.sh" || die "Failed to source: lib.sh"
  ```

### 13. Misc
- **Time**: Use `printf` built-ins (`%(fmt)T`) instead of `date` to avoid subprocesses.
- **Redirects**: Prefer bash-specific redirect operators for readability:
  ```bash
  # redirect stdout and stderr to file
  command &> file.log      # instead of: command > file.log 2>&1

  # pipe stdout and stderr
  command |& another       # instead of: command 2>&1 | another

  # discard all output
  command &> /dev/null     # instead of: command > /dev/null 2>&1
  ```
- **Here-string `<<<`**: Use here-string to pass variable content to stdin without spawning a subshell:
  ```bash
  # good: no subshell
  grep 'pattern' <<< "$content"
  jq '.field' <<< "$json"

  # avoid: spawns subshell for echo
  echo "$content" | grep 'pattern'
  ```
- **Quoting**: Use single quotes for literals; double quotes only for variable or command expansion:
  ```bash
  # single quotes: literals, fixed strings, empty strings
  local fallback=''
  local method='GET'
  grep --fixed-strings 'error:' "$log_file"

  # double quotes: variables, command substitution, interpolation
  echo "Processing: $filename"
  result="$(some_command)"

  # empty line output: just echo without arguments
  echo
  ```
- **Verbosity & Long-form Flags**: Script verbosity is essential for clarity and long-term maintenance. Always use long-form flags instead of short-form flags for all command-line utilities (e.g., `grep`, `curl`, `jq`) whenever they are available:
  ```bash
  curl --location --insecure --request 'GET' --output 'file.txt' "$url"
  ```
- **Arrays for Command Arguments**: When passing a variable list of arguments to a command, use arrays with `"${arr[@]}"` expansion. This preserves quoting and handles arguments with spaces correctly:
  ```bash
  # arrays
  local -a curl_args=(
      '--location'
      '--silent'
      '--max-time' '30'
  )

  # code
  if (( verbose )); then
      curl_args+=( '--verbose' )
  fi

  curl "${curl_args[@]}" "$url"
  ```
  **Array formatting rules:**
  - Multi-element initialization must be on separate lines (one element per line)
  - Quote elements with single quotes (or double if interpolation needed)
  - This enables proper syntax highlighting and handles elements with spaces/special characters
  - Single-element additions like `+=( '--verbose' )` can stay on one line
- **Table Output**: When printing tables, use `printf` with fixed-width format specifiers (`%-N.Ns`). Define the format string once and reuse it for both header and data rows:
  ```bash
  # consts
  local -r fmt='%-12.12s %-8.8s %-20.20s\n'

  # code: header and rows use same format
  # format string is a constant defined above, safe to use as variable
  # shellcheck disable=SC2059
  {
      printf "$fmt" 'NAME' 'STATUS' 'MESSAGE'
      printf "$fmt" '---' '---' '---'
      for item in "${items[@]}"; do
          printf "$fmt" "$name" "$status" "$message"
      done
  }
  ```
  This is a justified use of `shellcheck disable=SC2059` — the format string is a constant, and reusing it ensures consistent column widths across header and data rows.
- **Humanize Large Numbers**: For scripts focused on table output with large numeric values, humanize them like `du -h` or `df -h` (1K, 2.5M, 1.2G). Skip this for general-purpose scripts — it's overengineering if not needed:
  ```bash
  function humanize_bytes {
      # args
      local -r bytes="$1"

      # code
      if (( bytes >= 1073741824 )); then
          printf '%.1fG' "$(echo "scale=1; $bytes / 1073741824" | bc)"
      elif (( bytes >= 1048576 )); then
          printf '%.1fM' "$(echo "scale=1; $bytes / 1048576" | bc)"
      elif (( bytes >= 1024 )); then
          printf '%.1fK' "$(echo "scale=1; $bytes / 1024" | bc)"
      else
          printf '%dB' "$bytes"
      fi
  }
  ```

### 14. Documentation
- **shellcheck disable**: Use `# shellcheck disable=SCxxxx` only as a **last resort** when there is no way to fix or refactor the code. Always try to fix the underlying issue first. If disabling is unavoidable, ALWAYS add a comment on the preceding line explaining why it cannot be fixed:
  ```bash
  # nameref intentionally modifies caller's variable, not a bug
  # shellcheck disable=SC2034
  input_ref="$temp"
  ```
