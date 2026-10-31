"""Test Note and NotesList using fake ScriptingBridge objects"""

import pathlib
import shutil
from datetime import datetime

import Foundation
import pytest

import macnotesapp.notesapp as notesapp
from macnotesapp.database import NoteRecord, NotesDatabase
from macnotesapp.errors import DatabaseUnavailableError
from macnotesapp.notesapp import (
    Account,
    DatabaseNotes,
    Note,
    NotesApp,
    NotesList,
    ScriptingBridgeError,
)

from .fakes import (
    FakeDatabase,
    FakeSBAccount,
    FakeSBContainer,
    FakeSBNote,
    FakeSBNotesArray,
    nsdate,
)


@pytest.fixture
def no_applescript(monkeypatch):
    """Fail the test if AppleScript is called"""

    def fail(*args):
        raise AssertionError(f"AppleScript called: {args}")

    monkeypatch.setattr(notesapp, "run_script", fail)


def test_note_account_from_constructor(no_applescript):
    """#78: account passed at construction avoids an AppleScript round trip"""
    note = Note(FakeSBNote(id="x-coredata://A/ICNote/p1"), account="iCloud")
    assert note.account == "iCloud"


def test_note_account_cached(monkeypatch):
    calls = []

    def run_script(*args):
        calls.append(args)
        return "iCloud"

    monkeypatch.setattr(notesapp, "run_script", run_script)
    note = Note(FakeSBNote(id="x-coredata://A/ICNote/p1"))
    assert note.account == "iCloud"
    assert note.account == "iCloud"
    assert len(calls) == 1


def test_note_id_missing_raises():
    """#77: Note.id raises instead of returning 0"""
    with pytest.raises(ScriptingBridgeError):
        _ = Note(FakeSBNote(id=0)).id


def test_note_folder_container_none(monkeypatch):
    """#77: Note.folder falls back to AppleScript when container() is None"""
    note = Note(FakeSBNote(id="p1", container=None), account="iCloud")
    monkeypatch.setattr(note, "_run_script", lambda script: "Recovered")
    assert note.folder == "Recovered"


def test_note_folder_from_container(no_applescript):
    note = Note(
        FakeSBNote(id="p1", container=FakeSBContainer("Work")), account="iCloud"
    )
    assert note.folder == "Work"


def test_note_eq(no_applescript):
    a = Note(FakeSBNote(id="p1"), account="iCloud")
    b = Note(FakeSBNote(id="p1"), account="iCloud")
    c = Note(FakeSBNote(id="p2"), account="iCloud")
    assert a == b
    assert a != c
    assert a != "p1"
    assert len({a, b, c}) == 2


def _sbnote(i, folder="Notes"):
    return FakeSBNote(
        id=f"p{i}",
        name=f"name{i}",
        body=f"<div>body{i}</div>",
        plaintext=f"body{i}",
        creationDate=nsdate(datetime(2026, 1, i)),
        modificationDate=nsdate(datetime(2026, 2, i)),
        passwordProtected=False,
        container=FakeSBContainer(folder),
    )


def test_noteslist_partial_bulk_failure_stays_aligned():
    """#77: one account's failed bulk fetch must not misalign fields"""
    account1 = FakeSBNotesArray([_sbnote(1), _sbnote(2)])
    # bulk body fails (None) and bulk plaintext is empty, as seen on some macOS versions
    account2 = FakeSBNotesArray(
        [_sbnote(3, "Work")], bulk={"body": None, "plaintext": []}
    )
    noteslist = NotesList(account1, account2)
    records = noteslist.asdict()
    assert [r["id"] for r in records] == ["p1", "p2", "p3"]
    assert [r["body"] for r in records] == [
        "<div>body1</div>",
        "<div>body2</div>",
        "<div>body3</div>",
    ]
    assert [r["plaintext"] for r in records] == ["body1", "body2", "body3"]
    assert [r["folder"] for r in records] == ["Notes", "Notes", "Work"]
    assert records[2]["creation_date"] == datetime(2026, 1, 3)
    assert records[0]["password_protected"] is False
    assert len(noteslist) == 3


def test_noteslist_missing_values():
    """Missing string values are returned as empty strings, others as None"""

    note = FakeSBNote(id="p1", body=None, container=None)
    noteslist = NotesList(
        FakeSBNotesArray([note], bulk={"plaintext": [Foundation.NSNull.null()]})
    )
    assert noteslist.body == [""]
    assert noteslist.plaintext == [""]
    assert noteslist.container == [None]


def test_noteslist_account_and_asdict_without_body():
    noteslist = NotesList(
        FakeSBNotesArray([_sbnote(1), _sbnote(2)]),
        FakeSBNotesArray([_sbnote(3)]),
        accounts=["iCloud", "On My Mac"],
    )
    assert noteslist.account == ["iCloud", "iCloud", "On My Mac"]
    records = noteslist.asdict(body=False)
    assert [r["account"] for r in records] == ["iCloud", "iCloud", "On My Mac"]
    assert "body" not in records[0] and "plaintext" not in records[0]
    assert NotesList(FakeSBNotesArray([_sbnote(1)])).account == [None]


def _record(i, folder="Notes", tags=()):
    return NoteRecord(
        id=f"x-coredata://A/ICNote/p{i}",
        name=f"record{i}",
        account="iCloud",
        account_id="x-coredata://A/ICAccount/p1",
        folder=folder,
        folder_path=f"Parent/{folder}",
        plaintext=f"text{i}",
        creation_date=datetime(2026, 3, i),
        modification_date=datetime(2026, 4, i),
        password_protected=False,
        pinned=False,
        tags=tags,
    )


def _sb_for_record(i):
    return FakeSBNote(id=f"x-coredata://A/ICNote/p{i}", body=f"<div>sb{i}</div>")


def test_note_from_record_does_not_ask_notes(no_applescript):
    """#22: a note read from the database doesn't use AppleScript for its folder"""
    # the fake SB note has only id and body, so reading anything else from it fails
    note = Note(_sb_for_record(1), account="iCloud", record=_record(1, "Work"))
    assert note.id == "x-coredata://A/ICNote/p1"
    assert note.name == "record1"
    assert note.folder == "Work"
    assert note.folder_path == "Parent/Work"
    assert note.plaintext == "text1"
    assert note.creation_date == datetime(2026, 3, 1)
    assert note.modification_date == datetime(2026, 4, 1)
    assert note.password_protected is False
    assert note.body == "<div>sb1</div>"


def test_note_changes_forget_record(monkeypatch):
    database = FakeDatabase()
    sbnote = FakeSBNote(id="x-coredata://A/ICNote/p1", name="old")
    sbnote.setValue_forKey_ = lambda value, key: sbnote._props.update({key: value})
    note = Note(sbnote, account="iCloud", record=_record(1), database=database)
    assert note.name == "record1"
    note.name = "new"
    assert note.name == "new"
    # the next read waits for the note's saved state to change
    assert database.writes == [(note.id, "title", ("state", note.id, "title"))]


def test_imap_note_changes_do_not_wait_for_database(monkeypatch):
    """IMAP notes aren't in the database, so changing them must not wait for it"""
    monkeypatch.setattr(notesapp, "run_script", lambda *args: None)
    database = FakeDatabase()
    note = Note(
        FakeSBNote(id="x-coredata://B/IMAPNote/p1"), account="Google", database=database
    )
    note.delete()
    assert database.writes == []


def test_note_database_properties():
    record = _record(1, tags=("travel",))
    database = FakeDatabase([record], features={record.id: ["tables"]})
    note = Note(_sb_for_record(1), account="iCloud", database=database)
    assert note.tags == ["travel"]
    assert note.content_features() == ["tables"]
    backed = Note(_sb_for_record(1), account="iCloud", record=record)
    assert backed.asdict()["tags"] == ["travel"]
    assert backed.asdict()["folder_path"] == "Parent/Notes"

    missing = Note(FakeSBNote(id="x-coredata://B/IMAPNote/p1"), database=database)
    with pytest.raises(DatabaseUnavailableError):
        _ = missing.tags
    without_database = Note(_sb_for_record(1), account="iCloud")
    with pytest.raises(DatabaseUnavailableError):
        without_database.content_features()


def test_noteslist_mixes_database_and_scriptingbridge():
    sb_notes = FakeSBNotesArray([_sb_for_record(1), _sb_for_record(2)])
    database_notes = DatabaseNotes(
        [_record(2, tags=("a", "b")), _record(1)], sb_notes, "iCloud", FakeDatabase()
    )
    noteslist = NotesList(
        database_notes,
        FakeSBNotesArray([_sbnote(3, "Work")]),
        accounts=["iCloud", "Google"],
    )
    records = noteslist.asdict()
    assert [r["id"] for r in records] == [
        "x-coredata://A/ICNote/p2",
        "x-coredata://A/ICNote/p1",
        "p3",
    ]
    assert [r["account"] for r in records] == ["iCloud", "iCloud", "Google"]
    assert [r["body"] for r in records] == [
        "<div>sb2</div>",
        "<div>sb1</div>",
        "<div>body3</div>",
    ]
    assert [r["plaintext"] for r in records] == ["text2", "text1", "body3"]
    assert [r["folder"] for r in records] == ["Notes", "Notes", "Work"]
    assert [r["folder_path"] for r in records] == ["Parent/Notes", "Parent/Notes", None]
    assert [r["tags"] for r in records] == [["a", "b"], [], None]
    assert records[0]["creation_date"] == datetime(2026, 3, 2)
    assert len(noteslist) == 3
    assert [n.name for n in database_notes.notes()] == ["record2", "record1"]


def test_notesapp_backend_validated():
    with pytest.raises(ValueError):
        NotesApp(backend="sqlite")


def test_unsaved_changes_read_from_notes_app(tmp_path, no_applescript):
    """Notes changed but not yet saved by Notes.app are read from Notes.app"""
    path = tmp_path / "NoteStore.sqlite"
    shutil.copy(
        pathlib.Path(__file__).parent / "data" / "NoteStore-macOS-26-Tahoe.sqlite", path
    )
    database = NotesDatabase(path)
    [(account_id, account_name)] = database.accounts.items()
    saved = {r.name: r for r in database.notes()}["This is a note"]
    renamed = FakeSBNote(
        id=saved.id,
        name="Renamed in memory",
        plaintext="Renamed in memory\n",
        container=FakeSBContainer("Notes"),
        creationDate=nsdate(datetime(2026, 1, 1)),
        modificationDate=nsdate(datetime(2026, 1, 2)),
        passwordProtected=False,
    )
    account = Account(
        FakeSBAccount(FakeSBNotesArray([renamed])),
        database=database,
        name=account_name,
        id=account_id,
    )
    database.notify_write(saved.id, "title", database.note_state(saved.id, "title"))
    # a change to a note that isn't in this account is ignored
    database.notify_write(saved.id.replace("/p27", "/p999"), "modified", None)

    [found] = account.notes(name=["renamed in memory"], exact_name=True)
    assert found.id == saved.id
    assert found.folder == "Notes" and found.folder_path == "Notes"
    assert account.notes(name=["This is a note"], exact_name=True) == []
    assert len(account) == len(database.notes())
    database.close()
