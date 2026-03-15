"""Tests for fix-enabled-plugins.py.

Run: pytest test_fix_enabled_plugins.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "fix-enabled-plugins.py"


def setup_env(tmp_path, *, plugins_json=None, settings_json=None):
    """Create fake ~/.claude structure in tmp_path."""
    claude = tmp_path / ".claude"
    (claude / "plugins").mkdir(parents=True)
    if plugins_json is not None:
        (claude / "plugins" / "installed_plugins.json").write_text(
            json.dumps(plugins_json)
        )
    if settings_json is not None:
        (claude / "settings.json").write_text(json.dumps(settings_json))
    return claude


def run_script(tmp_path, stdin_text=None):
    """Run script with HOME pointed at tmp_path."""
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        input=stdin_text,
        timeout=5,
    )
    return r.returncode, r.stdout, r.stderr


def read_settings(tmp_path):
    return json.loads((tmp_path / ".claude" / "settings.json").read_text())


class TestErrorCases:
    def test_no_installed_plugins_file(self, tmp_path):
        setup_env(tmp_path)
        rc, out, err = run_script(tmp_path)
        assert rc == 1
        assert "not found" in err

    def test_plugins_field_is_list(self, tmp_path):
        setup_env(tmp_path, plugins_json={"plugins": ["a", "b"]})
        rc, out, err = run_script(tmp_path)
        assert rc == 1
        assert "not a dict" in err

    def test_corrupted_settings_json(self, tmp_path):
        setup_env(tmp_path, plugins_json={"plugins": {"a@x": {}}})
        (tmp_path / ".claude" / "settings.json").write_text("{broken")
        rc, out, err = run_script(tmp_path)
        assert rc == 1
        assert "not valid JSON" in err


class TestNoopCases:
    def test_empty_plugins_dict(self, tmp_path):
        setup_env(tmp_path, plugins_json={"plugins": {}})
        rc, out, err = run_script(tmp_path)
        assert rc == 0
        assert "zero plugins" in out

    def test_already_synced(self, tmp_path):
        setup_env(
            tmp_path,
            plugins_json={"plugins": {"a@x": {}}},
            settings_json={"enabledPlugins": {"a@x": True}},
        )
        rc, out, err = run_script(tmp_path)
        assert rc == 0
        assert "Nothing to do" in out


class TestEnabling:
    def test_no_settings_file(self, tmp_path):
        setup_env(tmp_path, plugins_json={"plugins": {"foo@bar": {}, "baz@qux": {}}})
        rc, out, err = run_script(tmp_path)
        assert rc == 0
        assert "Not enabled (2)" in out
        s = read_settings(tmp_path)
        assert s["enabledPlugins"] == {"foo@bar": True, "baz@qux": True}

    def test_non_bool_value_detected_as_missing(self, tmp_path):
        setup_env(
            tmp_path,
            plugins_json={"plugins": {"a@x": {}, "b@y": {}}},
            settings_json={"enabledPlugins": {"a@x": True, "b@y": "false"}},
        )
        rc, out, err = run_script(tmp_path)
        assert rc == 0
        assert "Not enabled (1)" in out
        assert "+ b@y" in out

    def test_preserves_other_settings_keys(self, tmp_path):
        setup_env(
            tmp_path,
            plugins_json={"plugins": {"new@p": {}}},
            settings_json={"enabledPlugins": {}, "otherKey": 42},
        )
        rc, out, err = run_script(tmp_path)
        assert rc == 0
        s = read_settings(tmp_path)
        assert s["otherKey"] == 42
        assert s["enabledPlugins"] == {"new@p": True}


class TestStalePlugins:
    def test_cancel_preserves_stale(self, tmp_path):
        setup_env(
            tmp_path,
            plugins_json={"plugins": {"a@x": {}}},
            settings_json={"enabledPlugins": {"a@x": True, "old@gone": True}},
        )
        rc, out, err = run_script(tmp_path, stdin_text="n\n")
        assert rc == 0
        assert "Cancelled" in out
        s = read_settings(tmp_path)
        assert "old@gone" in s["enabledPlugins"]

    def test_confirm_removes_stale(self, tmp_path):
        setup_env(
            tmp_path,
            plugins_json={"plugins": {"a@x": {}}},
            settings_json={"enabledPlugins": {"a@x": True, "old@gone": True}},
        )
        rc, out, err = run_script(tmp_path, stdin_text="y\n")
        assert rc == 0
        assert "Updated" in out
        s = read_settings(tmp_path)
        assert s["enabledPlugins"] == {"a@x": True}


class TestBackup:
    def test_backup_created(self, tmp_path):
        setup_env(
            tmp_path,
            plugins_json={"plugins": {"a@x": {}}},
            settings_json={"enabledPlugins": {}},
        )
        rc, out, err = run_script(tmp_path)
        assert rc == 0
        assert "Backup:" in out
        backups = list((tmp_path / ".claude").glob("settings.json.*.bak"))
        assert len(backups) == 1
