"""Test CLI argument handling and note selection without using Notes.app"""

import pytest
from click.testing import CliRunner

import macnotesapp
from macnotesapp.cli import cli as cli_module
from macnotesapp.cli.cli import cli_main, resolve_note

from .fakes import FakeNote, FakeNotesApp


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_app(monkeypatch):
    """Replace NotesApp in the CLI with a fake"""
    app = FakeNotesApp(
        [
            FakeNote("Food Log", "x-coredata://A/ICNote/p1"),
            FakeNote("Log", "x-coredata://A/ICNote/p2", folder="Work"),
            FakeNote("Changelog", "x-coredata://A/ICNote/p3"),
            FakeNote("Dup", "x-coredata://A/ICNote/p4"),
            FakeNote("dup", "x-coredata://A/ICNote/p5", account="On My Mac"),
            FakeNote(
                "Rich",
                "x-coredata://A/ICNote/p6",
                body="<div><h1>Rich</h1></div><table></table>",
            ),
            FakeNote("Attached", "x-coredata://A/ICNote/p7", attachments=["a"]),
        ]
    )
    monkeypatch.setattr(macnotesapp, "NotesApp", lambda: app)
    return app


@pytest.mark.parametrize("command", ["add", "cat", "edit", "list", "delete"])
def test_dash_h_is_help(runner, command):
    """#73: -h shows help for every command"""
    result = runner.invoke(cli_main, [command, "-h"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output


@pytest.mark.parametrize("command", ["add", "cat", "edit"])
def test_html_short_flag(runner, command):
    result = runner.invoke(cli_main, [command, "--help"])
    assert "-H, --html" in result.output


def test_resolve_exact_by_default(fake_app):
    """#74: names match exactly by default, not by substring"""
    note = resolve_note(fake_app, "log", None, None)
    assert note.id.endswith("p2")
    assert fake_app.calls[-1]["exact_name"] is True


def test_resolve_contains_ambiguous(fake_app, capsys):
    """#74: more than one match is an error that lists the candidates"""
    with pytest.raises(SystemExit) as exc:
        resolve_note(fake_app, "log", None, None, contains=True)
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "3 notes match" in err
    for i in (1, 2, 3):
        assert f"--id x-coredata://A/ICNote/p{i}" in err


def test_resolve_ambiguous_exact(fake_app, capsys):
    with pytest.raises(SystemExit):
        resolve_note(fake_app, "dup", None, None)
    assert "2 notes match" in capsys.readouterr().err


def test_resolve_not_found_hint(fake_app, capsys):
    with pytest.raises(SystemExit):
        resolve_note(fake_app, "foo", None, None)
    assert "--contains" in capsys.readouterr().err


def test_resolve_by_id(fake_app):
    note = resolve_note(fake_app, None, "x-coredata://A/ICNote/p4", None)
    assert note.name == "Dup"


def test_resolve_requires_name_or_id(fake_app):
    with pytest.raises(SystemExit):
        resolve_note(fake_app, None, None, None)
    with pytest.raises(SystemExit):
        resolve_note(fake_app, "Dup", "x-coredata://A/ICNote/p4", None)


def test_delete_substring_does_not_delete(runner, fake_app):
    """#74: `notes delete -y food` must not delete 'Food Log'"""
    result = runner.invoke(cli_main, ["delete", "-y", "food"])
    assert result.exit_code == 1
    assert not any(n.deleted for n in fake_app._notes)


def test_delete_exact(runner, fake_app):
    result = runner.invoke(cli_main, ["delete", "-y", "food log"])
    assert result.exit_code == 0, result.output
    assert "Deleted 'Food Log'" in result.output
    assert fake_app._notes[0].deleted


def test_rename_usage(runner, fake_app):
    result = runner.invoke(cli_main, ["rename", "only-one"])
    assert result.exit_code == 1
    assert "OLD_NAME NEW_NAME" in result.output
    result = runner.invoke(cli_main, ["rename", "--id", "x", "a", "b"])
    assert result.exit_code == 1
    assert "--id ID NEW_NAME" in result.output


def test_rename_by_id(runner, fake_app):
    result = runner.invoke(
        cli_main, ["rename", "--id", "x-coredata://A/ICNote/p4", "New"]
    )
    assert result.exit_code == 0, result.output
    assert fake_app._notes[3].name == "New"


def test_edit_body_keeps_title_and_escapes(runner, fake_app):
    """#75, #76: --body keeps the title and escapes plain text"""
    result = runner.invoke(cli_main, ["edit", "Log", "--body", "a < b\nc"])
    assert result.exit_code == 0, result.output
    assert fake_app._notes[1].body == (
        "<div><h1>Log</h1></div>\n<div>a &lt; b</div>\n<div>c</div>\n"
    )


def test_edit_refuses_attachments(runner, fake_app):
    """#75: replacing the body of a note with attachments requires --force"""
    result = runner.invoke(cli_main, ["edit", "Attached", "--body", "x"])
    assert result.exit_code == 1
    assert "1 attachment(s)" in result.output
    result = runner.invoke(cli_main, ["edit", "Attached", "--body", "x", "--force"])
    assert result.exit_code == 0, result.output


def test_edit_refuses_lossy_markdown(runner, fake_app, monkeypatch):
    """#75: editing a rich note as Markdown requires --html or --force"""
    edited = []
    monkeypatch.setattr(
        cli_module.click, "edit", lambda text, **kw: edited.append(text) or None
    )
    # don't read or create the user's real config file
    monkeypatch.setattr(
        cli_module, "ConfigSettings", lambda: type("C", (), {"editor": None})()
    )
    result = runner.invoke(cli_main, ["edit", "Rich"])
    assert result.exit_code == 1
    assert "tables" in result.output
    assert "--html" in result.output
    assert not edited

    result = runner.invoke(cli_main, ["edit", "Rich", "--html"])
    assert result.exit_code == 0, result.output
    assert edited == ["<div><h1>Rich</h1></div><table></table>"]
    assert "No changes made" in result.output


def test_edit_html_and_markdown_exclusive(runner, fake_app):
    result = runner.invoke(cli_main, ["edit", "Log", "-H", "-m", "--body", "x"])
    assert result.exit_code == 1
