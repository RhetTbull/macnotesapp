"""Fixtures for unit tests, which must never talk to Notes.app"""

import pytest

from macnotesapp.cli import cli as cli_module


@pytest.fixture(autouse=True)
def no_permission_check(monkeypatch):
    """Skip the Automation permission check, which sends an Apple Event to Notes"""
    monkeypatch.setattr(cli_module, "check_automation_permission", lambda: None)


@pytest.fixture(autouse=True)
def unsaved_changes_file(monkeypatch, tmp_path):
    """Keep the CLI's record of unsaved changes out of the user's state directory"""
    path = tmp_path / "state" / "unsaved_changes.json"
    monkeypatch.setattr(cli_module, "UNSAVED_CHANGES_FILE", path)
    return path
