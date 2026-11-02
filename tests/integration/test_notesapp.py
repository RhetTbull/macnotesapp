"""Integration tests for the library API against Notes.app"""

import pathlib
import time

import pytest

from macnotesapp.database import NotesDatabase
from macnotesapp.errors import (
    ContentLossError,
    DatabaseUnavailableError,
    FolderNotFoundError,
    MacNotesAppError,
)
from macnotesapp.formatting import text_to_html
from macnotesapp.notesapp import title_html

from .conftest import png_file, saved_attachments, wait_until_saved

ATTACHMENT_PATH = pathlib.Path(__file__).parent.parent / "attachment.txt"


def test_accounts(notesapp, account):
    accounts = notesapp.accounts
    assert accounts
    assert notesapp.default_account in accounts
    assert account.name == notesapp.default_account
    assert account.id
    assert account.default_folder in account.folders


def test_sandbox_folder(account, sandbox):
    assert sandbox in account.folders
    assert account.folder(sandbox).name == sandbox


def test_make_note(notesapp, account, sandbox, note_name):
    name = f"{note_name} & <title>"
    note = account.make_note(name, text_to_html("line 1\nline <2> & 3"), sandbox)
    assert note.id.startswith("x-coredata://")
    assert note.name == name
    assert note.folder == sandbox
    assert note.account == account.name
    assert "line 1\nline <2> & 3" in note.plaintext
    assert not note.password_protected
    assert note.creation_date <= note.modification_date


def test_find_notes(notesapp, account, sandbox, note_name):
    note = account.make_note(note_name, text_to_html("findable body"), sandbox)

    exact = notesapp.notes(name=[note_name.upper()], exact_name=True)
    assert exact == [note]
    assert notesapp.notes(name=[note_name[:-3]], exact_name=True) == []
    assert note in notesapp.notes(name=[note_name[:-3]])
    assert notesapp.notes(id=[note.id]) == [note]
    assert note in notesapp.notes(text=[note_name], accounts=[account.name])

    noteslist = notesapp.noteslist(
        name=[note_name], exact_name=True, accounts=[account.name]
    )
    records = noteslist.asdict()
    assert len(records) == 1
    assert records[0]["id"] == note.id
    assert records[0]["account"] == account.name
    assert records[0]["folder"] == sandbox
    assert "findable body" in records[0]["plaintext"]


def test_set_name_and_body(notesapp, account, sandbox, note_name):
    note = account.make_note(note_name, text_to_html("old body"), sandbox)
    new_name = f"{note_name} renamed"
    note.name = new_name
    assert note.name == new_name

    note.body = title_html(new_name) + text_to_html("new body")
    assert note.name == new_name
    assert "new body" in note.plaintext
    assert "old body" not in note.plaintext
    # a new query sees the change
    [found] = notesapp.notes(name=[new_name], exact_name=True)
    assert found == note and found.name == new_name
    assert "new body" in found.plaintext


@pytest.mark.xfail(reason="Notes.app can take more than 5 s to save a rename (#86)")
def test_rename_is_saved(account, sandbox, note_name):
    try:
        database = NotesDatabase()
    except DatabaseUnavailableError as e:
        pytest.skip(f"Notes database not readable: {e}")
    note = account.make_note(note_name, text_to_html("body"), sandbox)
    new_name = f"{note_name} renamed"
    note.name = new_name
    deadline = time.monotonic() + 5
    while (saved := database.note(note.id)) is None or saved.name != new_name:
        if time.monotonic() > deadline:
            break
        time.sleep(0.2)
    database.close()
    assert saved and saved.name == new_name


def test_move(notesapp, account, sandbox, sandbox2, note_name):
    note = account.make_note(note_name, text_to_html("move me"), sandbox)
    note.move(sandbox2)
    assert note.folder == sandbox2
    [found] = notesapp.notes(id=[note.id])
    assert found.folder == sandbox2


def test_database_properties(notesapp, account, sandbox, note_name):
    """Properties only the Notes database has"""
    if notesapp.database is None:
        pytest.skip("Notes database not used")
    plain = account.make_note(note_name, text_to_html("plain"), sandbox)
    assert plain.content_features() == []
    assert plain.tags == []
    assert plain.folder_path == sandbox
    bold = account.make_note(
        f"{note_name} bold", "<div><b>bold</b> and <i>italic</i></div>", sandbox
    )
    assert bold.content_features() == ["bold or italic"]
    [record] = notesapp.noteslist(name=[note_name], exact_name=True).asdict(body=False)
    assert record["folder_path"] == sandbox
    assert record["tags"] == []


def test_make_note_formats(account, sandbox, note_name, backend):
    """#39, #37: bodies can be text, Markdown, or HTML"""
    text = account.make_note(note_name, "line 1\nline <2>", sandbox, format="text")
    assert "line 1\nline <2>" in text.plaintext
    markdown = account.make_note(
        f"{note_name} md", "- one\n- two\n\n**bold**", sandbox, format="markdown"
    )
    assert "one\ntwo\nbold" in markdown.plaintext
    if backend == "database":
        wait_until_saved(markdown.id)
        assert {"lists", "bold or italic"} <= set(markdown.content_features())


def test_make_note_with_attachments(account, sandbox, note_name, tmp_path):
    """Attachments are copied into the note, and Notes.app shows them twice (#64)"""
    image = png_file(tmp_path / "image.png")
    note = account.make_note(
        note_name, "has attachments", sandbox, [ATTACHMENT_PATH, image], format="text"
    )
    assert sorted(a.name for a in note.attachments) == ["attachment.txt", "image.png"]
    attachments, references, stored = saved_attachments(note.id, 2)
    assert attachments == stored == ["public.plain-text", "public.png"]
    assert sorted(set(references)) == attachments
    # the source can go: the note has its own copy
    image.unlink()
    assert saved_attachments(note.id, 2)[2] == stored


def test_add_attachment(account, sandbox, note_name):
    """An added attachment is copied into the note, and Notes.app shows it twice (#64)"""
    note = account.make_note(note_name, "plain", sandbox, format="text")
    attachment = note.add_attachment(ATTACHMENT_PATH)
    assert attachment.name == "attachment.txt"
    assert [a.id for a in note.attachments] == [attachment.id]
    attachments, references, stored = saved_attachments(note.id, 1)
    assert attachments == stored == ["public.plain-text"]
    assert set(references) == {"public.plain-text"}


def test_append(account, sandbox, note_name, backend):
    """#51: append adds to the end, and refuses to lose attachments"""
    note = account.make_note(note_name, "first", sandbox, format="text")
    if backend == "database":
        wait_until_saved(note.id)
        note.append("second <line>")
    else:
        # without the database, content can't be checked
        with pytest.raises(ContentLossError, match="Can't check"):
            note.append("second <line>")
        note.append("second <line>", force=True)
    assert note.plaintext.rstrip().endswith("first\nsecond <line>")
    note.append("- item", format="markdown", force=True)
    assert note.plaintext.rstrip().endswith("item")

    attached = account.make_note(
        f"{note_name} att", "x", sandbox, [ATTACHMENT_PATH], format="text"
    )
    saved_attachments(attached.id, 1)
    with pytest.raises(ContentLossError) as e:
        attached.append("y")
    if backend == "database":
        assert e.value.features == ["attachments"]
    assert "y" not in attached.plaintext


def test_subfolders(notesapp, account, sandbox, note_name, run_id):
    """#4: make notes in, move notes to, and delete subfolders by path"""
    sub = f"{sandbox}/macnotesapp-test-sub-{run_id}"
    deeper = f"{sub}/macnotesapp-test-deeper-{run_id}"
    folder = account.make_folder(deeper, parents=True)
    assert folder.name == f"macnotesapp-test-deeper-{run_id}"
    assert {sub, deeper} <= set(account.folder_paths)
    with pytest.raises(MacNotesAppError, match="already exists"):
        account.make_folder(sub)
    assert (
        account.make_folder(sub, parents=True).name == f"macnotesapp-test-sub-{run_id}"
    )

    note = account.make_note(note_name, "nested", deeper, format="text")
    assert note.folder == f"macnotesapp-test-deeper-{run_id}"
    note.move(sub)
    assert note.folder == f"macnotesapp-test-sub-{run_id}"
    [found] = notesapp.notes(id=[note.id])
    assert found.folder == f"macnotesapp-test-sub-{run_id}"
    with pytest.raises(FolderNotFoundError):
        note.move(f"{sandbox}/missing")

    account.delete_folder(sub)
    paths = account.folder_paths
    assert sub not in paths and deeper not in paths
    # Notes.app would leave the subfolder behind, without a parent
    assert f"macnotesapp-test-deeper-{run_id}" not in paths


def test_delete(notesapp, account, sandbox, note_name):
    note = account.make_note(note_name, text_to_html("delete me"), sandbox)
    note.delete()
    # deleted notes move to Recently Deleted, so check the note left the sandbox
    remaining = notesapp.noteslist(
        name=[note_name], exact_name=True, accounts=[account.name]
    )
    assert sandbox not in remaining.folder


def test_make_and_delete_folder(account, run_id):
    name = f"macnotesapp-test-{run_id}-mkdir"
    folder = account.make_folder(name)
    try:
        assert folder.name == name
        assert name in account.folders
    finally:
        account.delete_folder(name)
    assert name not in account.folders
