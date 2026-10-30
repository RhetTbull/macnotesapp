"""Integration tests for the library API against Notes.app"""

import pathlib

import pytest

from macnotesapp.formatting import text_to_html
from macnotesapp.notesapp import title_html

from ..utils import get_macos_version

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


def test_set_name_and_body(account, sandbox, note_name):
    note = account.make_note(note_name, text_to_html("old body"), sandbox)
    new_name = f"{note_name} renamed"
    note.name = new_name
    assert note.name == new_name

    note.body = title_html(new_name) + text_to_html("new body")
    assert note.name == new_name
    assert "new body" in note.plaintext
    assert "old body" not in note.plaintext


def test_move(account, sandbox, sandbox2, note_name):
    note = account.make_note(note_name, text_to_html("move me"), sandbox)
    note.move(sandbox2)
    assert note.folder == sandbox2


@pytest.mark.skipif(
    get_macos_version() < (13, 0, 0), reason="Requires macOS 13.0 or higher"
)
@pytest.mark.xfail(reason="attachments are unreliable on recent macOS (#64)")
def test_add_attachment(account, sandbox, note_name):
    note = account.make_note(note_name, text_to_html("has attachment"), sandbox)
    attachment = note.add_attachment(ATTACHMENT_PATH)
    assert attachment.id
    assert [a.id for a in note.attachments] == [attachment.id]


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
