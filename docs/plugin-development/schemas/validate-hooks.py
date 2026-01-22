#!/usr/bin/env python3
"""
Validate hooks.json files against the official Claude Code hooks schema.
"""
import json
import sys
from pathlib import Path
from jsonschema import validate, ValidationError, SchemaError


def validate_hooks_file(hooks_path: Path, schema_path: Path) -> bool:
    """Validate a single hooks.json file."""
    try:
        with open(schema_path) as f:
            schema = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load schema: {e}")
        return False

    try:
        with open(hooks_path) as f:
            hooks = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {hooks_path}: {e}")
        return False
    except Exception as e:
        print(f"❌ Failed to load {hooks_path}: {e}")
        return False

    try:
        validate(hooks, schema)
        print(f"✅ {hooks_path} is valid")
        return True
    except ValidationError as e:
        print(f"❌ Validation error in {hooks_path}:")
        print(f"   Message: {e.message}")
        if e.path:
            path_str = " -> ".join(str(p) for p in e.path)
            print(f"   Path: {path_str}")
        return False
    except SchemaError as e:
        print(f"❌ Schema error: {e}")
        return False


def main():
    """Find and validate all hooks.json files."""
    script_dir = Path(__file__).parent
    schema_path = script_dir / "hooks.schema.json"

    if not schema_path.exists():
        print(f"❌ Schema not found: {schema_path}")
        sys.exit(1)

    # Find all hooks.json files
    repo_root = script_dir.parent.parent.parent
    hooks_files = list(repo_root.glob("*/hooks/hooks.json"))

    if not hooks_files:
        print("No hooks.json files found")
        sys.exit(0)

    print(f"Found {len(hooks_files)} hooks.json file(s)")
    print()

    all_valid = True
    for hooks_path in sorted(hooks_files):
        if not validate_hooks_file(hooks_path, schema_path):
            all_valid = False

    print()
    if all_valid:
        print(f"✅ All {len(hooks_files)} hooks.json files are valid")
        sys.exit(0)
    else:
        print("❌ Some hooks.json files failed validation")
        sys.exit(1)


if __name__ == "__main__":
    main()
