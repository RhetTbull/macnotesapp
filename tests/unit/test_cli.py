"""Test CLI argument handling and note selection without using Notes.app"""

import json
import pathlib
from datetime import datetime

import click
import pytest
from click.testing import CliRunner

import macnotesapp
from macnotesapp.cli import cli as cli_module
from macnotesapp.cli.cli import NotFoundError, cli_main, resolve_note
from macnotesapp.errors import UnsavedChangesError

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
                body="<div><h1>Rich</h1></div>\n<table></table>",
            ),
            FakeNote("Attached", "x-coredata://A/ICNote/p7", attachments=["a"]),
        ]
    )

    def notes_app(**kwargs):
        app.kwargs = kwargs
        return app

    monkeypatch.setattr(macnotesapp, "NotesApp", notes_app)
    return app


@pytest.mark.parametrize(
    "command", ["add", "cat", "edit", "list", "delete", "append", "mkdir"]
)
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


def test_resolve_contains_ambiguous(fake_app):
    """#74: more than one match is an error that lists the candidates"""
    with pytest.raises(click.ClickException) as exc:
        resolve_note(fake_app, "log", None, None, contains=True)
    assert exc.value.exit_code == 1
    message = exc.value.message
    assert "3 notes match" in message
    for i in (1, 2, 3):
        assert f"--id x-coredata://A/ICNote/p{i}" in message


def test_resolve_ambiguous_exact(fake_app):
    with pytest.raises(click.ClickException) as exc:
        resolve_note(fake_app, "dup", None, None)
    assert "2 notes match" in exc.value.message


def test_resolve_not_found_hint(fake_app):
    with pytest.raises(NotFoundError) as exc:
        resolve_note(fake_app, "foo", None, None)
    assert exc.value.exit_code == 3
    assert "--contains" in exc.value.message


def test_resolve_by_id(fake_app):
    note = resolve_note(fake_app, None, "x-coredata://A/ICNote/p4", None)
    assert note.name == "Dup"


def test_resolve_requires_name_or_id(fake_app):
    with pytest.raises(click.UsageError):
        resolve_note(fake_app, None, None, None)
    with pytest.raises(click.UsageError):
        resolve_note(fake_app, "Dup", "x-coredata://A/ICNote/p4", None)


def test_delete_substring_does_not_delete(runner, fake_app):
    """#74: `notes delete -y food` must not delete 'Food Log'"""
    result = runner.invoke(cli_main, ["delete", "-y", "food"])
    assert result.exit_code == 3
    assert not any(n.deleted for n in fake_app._notes)


def test_delete_exact(runner, fake_app):
    result = runner.invoke(cli_main, ["delete", "-y", "food log"])
    assert result.exit_code == 0, result.output
    assert "Deleted 'Food Log'" in result.output
    assert fake_app._notes[0].deleted


def test_rename_usage(runner, fake_app):
    result = runner.invoke(cli_main, ["rename", "only-one"])
    assert result.exit_code == 2
    assert "OLD_NAME NEW_NAME" in result.output
    result = runner.invoke(cli_main, ["rename", "--id", "x", "a", "b"])
    assert result.exit_code == 2
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
    assert edited == ["<div><h1>Rich</h1></div>\n<table></table>"]
    assert "No changes made" in result.output


def test_edit_html_and_markdown_exclusive(runner, fake_app):
    result = runner.invoke(cli_main, ["edit", "Log", "-H", "-m", "--body", "x"])
    assert result.exit_code == 2


def test_cat_not_found(runner, fake_app):
    result = runner.invoke(cli_main, ["cat", "nothing-matches"])
    assert result.exit_code == 3
    assert "No notes found" in result.output


def test_cat_json_markdown(runner, fake_app):
    """#79: cat --json --markdown outputs the body as Markdown with zoned dates"""
    fake_app._notes[1].body = "<div><b>bold</b> [not markup]</div>"
    result = runner.invoke(cli_main, ["cat", "--json", "--markdown", "Log"])
    assert result.exit_code == 0, result.output
    records = {r["name"]: r for r in json.loads(result.output)}
    assert records["Log"]["body"].strip() == "**bold** [not markup]"
    assert "plaintext" not in records["Log"]
    modified = datetime.fromisoformat(records["Log"]["modification_date"])
    assert modified.tzinfo is not None


def test_cat_raw_output_not_rich_markup(runner, fake_app):
    """#79: raw output is printed as is, not interpreted as Rich markup"""
    fake_app._notes[1].body = "<div>[bold]x[/bold]</div>"
    result = runner.invoke(cli_main, ["cat", "--html", "Log"])
    assert "<div>[bold]x[/bold]</div>" in result.output


def test_list_json(runner, fake_app):
    """#79: list --json outputs metadata"""
    result = runner.invoke(cli_main, ["list", "--json", "-a", "iCloud"])
    assert result.exit_code == 0, result.output
    records = json.loads(result.output)
    assert fake_app.calls[-1]["accounts"] == ["iCloud"]
    assert [r["name"] for r in records] == [n.name for n in fake_app._notes]
    assert set(records[0]) == {
        "account",
        "id",
        "name",
        "creation_date",
        "modification_date",
        "password_protected",
        "folder",
    }


def test_list_tag(runner, fake_app):
    result = runner.invoke(cli_main, ["list", "--json", "--tag", "work", "-t", "#home"])
    assert result.exit_code == 0, result.output
    assert fake_app.calls[-1]["tag"] == ["work", "#home"]


@pytest.mark.parametrize("backend", ["auto", "database", "scriptingbridge"])
def test_backend_option(runner, fake_app, backend):
    args = ["--backend", backend] if backend != "auto" else []
    result = runner.invoke(cli_main, [*args, "list", "--json"])
    assert result.exit_code == 0, result.output
    assert fake_app.kwargs == {"backend": backend}


def test_edit_uses_database_features(runner, fake_app, monkeypatch):
    """#75: checklists and tags, invisible in the HTML, block lossy edits"""
    monkeypatch.setattr(cli_module.click, "edit", lambda text, **kw: None)
    monkeypatch.setattr(
        cli_module, "ConfigSettings", lambda: type("C", (), {"editor": None})()
    )
    note = fake_app._notes[1]
    note.features = ["bold or italic", "checklists"]
    result = runner.invoke(cli_main, ["edit", "Log"])
    assert result.exit_code == 1
    assert "checklists" in result.output and "bold" not in result.output
    result = runner.invoke(cli_main, ["edit", "Log", "--html"])
    assert result.exit_code == 1
    # replacing the body only refuses for content that isn't text
    result = runner.invoke(cli_main, ["edit", "Log", "--body", "x"])
    assert result.exit_code == 0, result.output

    note.features = ["tags"]
    result = runner.invoke(cli_main, ["edit", "Log", "--body", "y"])
    assert result.exit_code == 1
    assert "tags" in result.output
    note.features = ["bold or italic", "links"]
    result = runner.invoke(cli_main, ["edit", "Log"])
    assert result.exit_code == 0, result.output


def test_unexpected_error_is_reported(runner, monkeypatch):
    """#79: errors are reported as a message with exit code 1, not a traceback"""

    def boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(macnotesapp, "NotesApp", boom)
    result = runner.invoke(cli_main, ["list"])
    assert result.exit_code == 1
    assert "Error: boom" in result.output
    assert "--debug" in result.output
    assert "Traceback" not in result.output

    result = runner.invoke(cli_main, ["--debug", "list"])
    assert isinstance(result.exception, RuntimeError)


def test_permission_error_is_reported(runner, monkeypatch):
    """#79: missing Automation permission gives instructions"""

    def denied():
        raise macnotesapp.NotesPermissionError()

    monkeypatch.setattr(cli_module, "check_automation_permission", denied)
    result = runner.invoke(cli_main, ["list"])
    assert result.exit_code == 1
    assert "Privacy & Security > Automation" in result.output


def test_unsaved_changes_passed_to_next_command(tmp_path, unsaved_changes_file):
    """Changes Notes.app hasn't saved yet are passed to the next CLI command"""
    import shutil

    from macnotesapp.database import NotesDatabase

    path = tmp_path / "NoteStore.sqlite"
    data = pathlib.Path(__file__).parent / "data" / "NoteStore-macOS-26-Tahoe.sqlite"
    shutil.copy(data, path)
    first, second = NotesDatabase(path), NotesDatabase(path)
    note_id = first.notes(name=["This is a note"], exact_name=True)[0].id
    first.notify_write(note_id, "folder", first.note_state(note_id, "folder"))

    cli_module.save_unsaved_changes(first)
    assert unsaved_changes_file.exists()
    cli_module.load_unsaved_changes(second)
    assert second.unsaved_note_ids() == {note_id}

    # once saved (or expired), the file is removed
    first._unsaved = []
    cli_module.save_unsaved_changes(first)
    assert not unsaved_changes_file.exists()
    first.close()
    second.close()


def test_unsaved_changes_file_damaged(unsaved_changes_file):
    unsaved_changes_file.parent.mkdir(parents=True)
    unsaved_changes_file.write_text("not json")
    database = type("D", (), {"notify_write": lambda self, *args: None})()
    cli_module.load_unsaved_changes(database)  # ignored, no error


# ---- Phase 3: add, append, and folder paths


@pytest.fixture
def config(monkeypatch):
    """Settings for `notes add` and `notes append` instead of the user's config file"""
    settings = type(
        "Config",
        (),
        {"format": "plaintext", "account": "iCloud", "folder": None, "editor": None},
    )()
    monkeypatch.setattr(cli_module, "ConfigSettings", lambda: settings)
    return settings


def test_add_markdown_title_and_attachments(runner, fake_app, config, tmp_path):
    """#13, #39, #64: the name is plain text, and files are attached"""
    path = tmp_path / "a.txt"
    path.write_text("x")
    result = runner.invoke(
        cli_main,
        ["add", "-m", "-f", "Work/Projects", "-A", str(path), "# Title\n\n**body**"],
    )
    assert result.exit_code == 0, result.output
    [made] = fake_app.fake_account.made_notes
    assert made == dict(
        name="Title",
        body="\n**body**",
        folder="Work/Projects",
        attachments=[str(path)],
        format="markdown",
    )


@pytest.mark.parametrize(
    "flag, format_, name",
    [
        ("-H", "html", "Tom & Jerry"),
        ("-p", "text", "<b>Tom &amp; Jerry</b>"),
        (None, "text", "<b>Tom &amp; Jerry</b>"),
    ],
)
def test_add_formats(runner, fake_app, config, flag, format_, name):
    args = ["add", *([flag] if flag else []), "<b>Tom &amp; Jerry</b>\nbody"]
    result = runner.invoke(cli_main, args)
    assert result.exit_code == 0, result.output
    [made] = fake_app.fake_account.made_notes
    assert (made["name"], made["format"]) == (name, format_)


def test_add_configured_format(runner, fake_app, config):
    config.format = "Markdown"
    result = runner.invoke(cli_main, ["add", "## Title\n- item"])
    assert result.exit_code == 0, result.output
    [made] = fake_app.fake_account.made_notes
    assert (made["name"], made["format"]) == ("Title", "markdown")


def test_add_missing_attachment(runner, fake_app, config, tmp_path):
    result = runner.invoke(cli_main, ["add", "-A", str(tmp_path / "missing"), "x"])
    assert result.exit_code == 2
    assert not fake_app.fake_account.made_notes


def test_append(runner, fake_app, config):
    """#51: append adds text to the end of a note"""
    fake_app._notes[1].features = []
    result = runner.invoke(cli_main, ["append", "Log", "more text"])
    assert result.exit_code == 0, result.output
    assert fake_app._notes[1].appended == ("more text", "text", False)
    assert "Appended to 'Log'" in result.output


def test_append_stdin_and_id(runner, fake_app, config):
    note = fake_app._notes[1]
    note.features = []
    result = runner.invoke(cli_main, ["append", "--id", note.id, "-m"], input="- a\n")
    assert result.exit_code == 0, result.output
    assert note.appended == ("- a", "markdown", False)
    result = runner.invoke(cli_main, ["append", "Log", "-"], input="<b>x</b>\n\n")
    assert result.exit_code == 0, result.output
    assert note.appended == ("<b>x</b>", "text", False)


def test_append_configured_format(runner, fake_app, config):
    config.format = "HTML"
    fake_app._notes[1].features = []
    result = runner.invoke(cli_main, ["append", "Log", "<b>x</b>"])
    assert result.exit_code == 0, result.output
    assert fake_app._notes[1].appended == ("<b>x</b>", "html", False)


def test_append_refuses_content_loss(runner, fake_app, config):
    """#51, #71: append refuses to lose content unless --force is given"""
    note = fake_app._notes[1]
    note.features = ["bold or italic", "checklists"]
    result = runner.invoke(cli_main, ["append", "Log", "x"])
    assert result.exit_code == 1
    assert "checklists" in result.output and "--force" in result.output
    assert not hasattr(note, "appended")
    result = runner.invoke(cli_main, ["append", "Log", "x", "--force"])
    assert result.exit_code == 0, result.output
    assert note.appended == ("x", "text", True)
    # without the database, the content can't be checked
    note.features = None
    result = runner.invoke(cli_main, ["append", "Log", "x"])
    assert result.exit_code == 1
    assert "Can't check" in result.output


@pytest.mark.parametrize(
    "args, exit_code, message",
    [
        (["append", "Log", "a", "b"], 2, "Expected: notes append NOTE_NAME [TEXT]"),
        (["append", "--id", "x-coredata://A/ICNote/p2", "Log", "a"], 2, "--id ID"),
        (["append", "-H", "-m", "Log", "a"], 2, "Only one of"),
        (["append", "Log", "  "], 1, "No text"),
        (["append", "Nope", "a"], 3, "not found"),
    ],
)
def test_append_usage(runner, fake_app, config, args, exit_code, message):
    result = runner.invoke(cli_main, args)
    assert result.exit_code == exit_code, result.output
    assert message in result.output


def test_move_missing_folder_is_not_found(runner, fake_app):
    result = runner.invoke(cli_main, ["move", "Log", "-f", "Missing"])
    assert result.exit_code == 3
    assert "Folder 'Missing' not found" in result.output


def test_move_to_subfolder(runner, fake_app):
    result = runner.invoke(cli_main, ["move", "Log", "-f", "Work/Projects"])
    assert result.exit_code == 0, result.output
    assert fake_app._notes[1].folder == "Work/Projects"


def test_mkdir_parents(runner, fake_app):
    result = runner.invoke(cli_main, ["mkdir", "-p", "A/B"])
    assert result.exit_code == 0, result.output
    assert fake_app.fake_account.made_folders == [("A/B", True)]


def test_rmdir_counts_subfolders(runner, fake_app):
    fake_app.fake_account.tree = macnotesapp.notesapp.FolderTree(
        ["w", "p", "y"], ["Work", "Projects", "2026"], [None, "w", "p"]
    )
    result = runner.invoke(cli_main, ["rmdir", "Work"], input="n\n")
    assert "Delete folder 'Work' and its 2 subfolder(s)" in result.output
    assert fake_app.fake_account.deleted_folders == []
    result = runner.invoke(cli_main, ["rmdir", "-y", "work/projects"])
    assert result.exit_code == 0, result.output
    # the folder confirmed is deleted, by its full path
    assert fake_app.fake_account.deleted_folders == ["Work/Projects"]
    assert "Deleted folder 'Work/Projects'" in result.output
    result = runner.invoke(cli_main, ["rmdir", "-y", "Missing"])
    assert result.exit_code == 3


def test_edit_refuses_unsaved_note(runner, fake_app):
    """The database has old content until Notes.app saves; the check without it
    misses checklists, so edit refuses unless forced"""
    note = fake_app._notes[1]
    note.features = UnsavedChangesError("Notes.app hasn't saved recent changes")
    result = runner.invoke(cli_main, ["edit", "Log", "--body", "x"])
    assert result.exit_code == 1
    assert "hasn't saved" in result.output and "--force" in result.output
    result = runner.invoke(cli_main, ["edit", "Log", "--body", "x", "--force"])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("args", [["-m", "#\nbody"], ["-H", "<!DOCTYPE html>\nbody"]])
def test_add_empty_name(runner, fake_app, config, args):
    result = runner.invoke(cli_main, ["add", *args])
    assert result.exit_code == 1
    assert "No note name" in result.output
    assert not fake_app.fake_account.made_notes
