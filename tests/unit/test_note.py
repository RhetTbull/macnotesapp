"""Test Note and NotesList using fake ScriptingBridge objects"""

from datetime import datetime

import Foundation
import pytest

import macnotesapp.notesapp as notesapp
from macnotesapp.notesapp import Note, NotesList, ScriptingBridgeError

from .fakes import FakeSBContainer, FakeSBNote, FakeSBNotesArray, nsdate


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
        Note(FakeSBNote(id=0)).id


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
