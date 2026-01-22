---
name: dignified-bash
description: Bash coding style guide. Apply these standards when writing, reviewing, or modifying any shell script, hook, or command-line tool. Triggers on: bash, shell, sh, .sh files, hooks, CLI scripts. Always use bash, never plain sh.
user-invocable: false
allowed-tools: Bash
---

# Bash Coding Style Guide

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

      echo "FATAL: ${message}" >&2
      exit "$code"
  }
  ```
- Usage:
  ```bash
  # assert: config file exists
  [[ -f "$config_file" ]] || die "Config file not found: $config_file"

  # assert: source library exists
  source "$lib_path" || die "Failed to source: $lib_path" 2
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
  - **Multiple declarations**: When declaring multiple variables of the same type, put them on one line:
    ```bash
    local network_mode container_name project project_dir
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

### 5. Associative Arrays (Dicts)
- Use associative arrays (`declare -A` / `local -A`) where they simplify code logic or improve readability.
- Good use cases: tracking state, caching lookups, grouping related data.
- Don't use them just for the sake of it — only when they provide a clear benefit.
  ```bash
  # dicts
  declare -A restarted_projects
  restarted_projects["myproject"]=1

  # dicts
  local -A config
  config["host"]="localhost"
  config["port"]="8080"
  ```

### 6. Arithmetic Context
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

### 7. Conditionals
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

### 8. Assertions & Early Returns
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

### 9. Implicit Return Code
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

### 10. Functions Structure
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

### 11. External Dependencies
- Explicitly pass global state (like configuration paths) as arguments to functions. Avoid hidden dependencies on global variables inside helper functions.
- Use `die()` for failed source:
  ```bash
  source "$script_dir/lib.sh" || die "Failed to source: lib.sh"
  ```

### 12. Misc
- **Time**: Use `printf` built-ins (`%(fmt)T`) instead of `date` to avoid subprocesses.
- **Quoting**: Use single quotes for literals; double quotes only for variable or command expansion.
- **Verbosity & Long-form Flags**: Script verbosity is essential for clarity and long-term maintenance. Always use long-form flags instead of short-form flags for all command-line utilities (e.g., `grep`, `curl`, `jq`) whenever they are available:
  ```bash
  curl --location --insecure --request 'GET' --output 'file.txt' "$url"
  ```

### 13. Documentation
- For `shellcheck disable` directives, ALWAYS add a comment on the preceding line explaining why it is disabled.
