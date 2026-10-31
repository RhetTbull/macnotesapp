"""Integration tests for the CLI against Notes.app"""

import json

import pytest
from click.testing import CliRunner

from macnotesapp.cli.cli import cli_main


@pytest.fixture
def notes(account):
    """Run a `notes` command and return the result"""
    runner = CliRunner()

    def run(*args, exit_code=0):
        result = runner.invoke(cli_main, list(args))
        assert result.exit_code == exit_code, result.output
        return result

    return run


def find(notes, account, name) -> list[dict]:
    """Return `notes list --json` records for notes named name"""
    result = notes("list", "--json", "-a", account.name, name)
    return [r for r in json.loads(result.output) if r["name"] == name]


def test_accounts(notes, account):
    data = json.loads(notes("accounts", "--json").output)
    assert account.name in data


def test_note_lifecycle(notes, account, sandbox, sandbox2, note_name):
    a = ["-a", account.name]
    notes("add", "-p", *a, "-f", sandbox, f"{note_name}\nfirst line\na < b")

    [record] = find(notes, account, note_name)
    assert record["folder"] == sandbox
    note_id = record["id"]

    [cat] = json.loads(notes("cat", "--json", "--plaintext", note_name).output)
    assert cat["id"] == note_id
    assert "first line\na < b" in cat["body"]

    new_name = f"{note_name} renamed"
    notes("rename", *a, note_name, new_name)
    assert find(notes, account, new_name)

    notes("move", *a, new_name, "-f", sandbox2)
    [record] = find(notes, account, new_name)
    assert record["folder"] == sandbox2

    notes("edit", *a, new_name, "--body", "replaced")
    [cat] = json.loads(notes("cat", "--json", "--plaintext", new_name).output)
    assert cat["name"] == new_name
    assert "replaced" in cat["body"]

    notes("delete", "-y", "--id", note_id)
    assert all(r["folder"] != sandbox2 for r in find(notes, account, new_name))


def test_ambiguous_name_refused(notes, account, sandbox, note_name):
    a = ["-a", account.name]
    notes("add", "-p", *a, "-f", sandbox, note_name)
    notes("add", "-p", *a, "-f", sandbox, note_name)
    result = notes("delete", "-y", *a, note_name, exit_code=1)
    assert "2 notes match" in result.output
    assert len(find(notes, account, note_name)) == 2


def test_not_found(notes, account, note_name):
    notes("delete", "-y", "-a", account.name, note_name, exit_code=3)
    notes("cat", note_name, exit_code=3)


def test_mkdir_rmdir(notes, account, run_id):
    name = f"macnotesapp-test-{run_id}-cli"
    notes("mkdir", "-a", account.name, name)
    try:
        assert name in account.folders
    finally:
        notes("rmdir", "-y", "-a", account.name, name)
    assert name not in account.folders
    notes("rmdir", "-y", "-a", account.name, name, exit_code=3)
