"""Test reading the Notes database using fixture databases in tests/unit/data

The macOS 12, 15, and 26 fixtures come from apple-notes-parser's tests. The macOS 27
fixture was made for macnotesapp. Each is a small On My Mac database with notes in
nested folders, a locked note, tags, a checklist, and an attachment; see FIXTURES.
"""

import gzip
import pathlib
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from apple_notes_parser.notestore_pb2 import NoteStoreProto

from macnotesapp import database
from macnotesapp.database import (
    CHANGE_COLUMNS,
    DatabaseUnavailableError,
    NotesDatabase,
    connect_read_only,
    note_data_features,
)

DATA = pathlib.Path(__file__).parent / "data"
TAHOE = "NoteStore-macOS-26-Tahoe.sqlite"
MACOS27 = "NoteStore-macOS-27.sqlite"


@dataclass(frozen=True)
class Fixture:
    """What a fixture database contains"""

    file: str
    plain: str  # a note without formatting in the default Notes folder
    buried: str  # a note three folders deep
    buried_path: str
    locked: str
    formatted: str
    formatting: set[str]  # some of the formatted note's content_features()
    tags: dict[str, tuple[str, ...]] = field(default_factory=dict)
    deleted: bool = True  # has a note in Recently Deleted

    def __str__(self):
        return self.file


FIXTURES = [
    Fixture(
        file="NoteStore-macOS-12-Monterey.sqlite",
        plain="This is a note",
        buried="This note is deeply buried",
        buried_path="Folder2/Subfolder/Subsubfolder",
        locked="This note is password protected",
        formatted="This note has special formatting",
        formatting={"checklists", "tables"},
    ),
    Fixture(
        file="NoteStore-macOS-15-Sequoia.sqlite",
        plain="This is a note",
        buried="This note is deeply buried",
        buried_path="Folder2/Subfolder/Subsubfolder",
        locked="This note is password protected",
        formatted="This note has special formatting",
        formatting={"checklists", "tables"},
        tags={"This note has tags": ("travel", "vacation")},
    ),
    Fixture(
        file=TAHOE,
        plain="This is a note",
        buried="This is a deeply buried note",
        buried_path="Folder2/Subfolder/Subsubfolder",
        locked="This note is password protected",
        formatted="This note has special formatting",
        formatting={"checklists", "tables"},
        tags={"This note has tags": ("travel", "vacation")},
    ),
    Fixture(
        file=MACOS27,
        plain="This is a plain text note",
        buried="This note is 3 levels deep in a folder",
        buried_path="Folder2/SubFolder/SubSubFolder",
        locked="This note is locked. The password is “foobar”",
        formatted="This note has text formatting",
        formatting={"headings", "lists", "bold or italic"},
        tags={
            "This note has a tag named “Test”": ("Test",),
            "This note has 2 tags: Test, todo": ("Test", "todo"),
        },
        deleted=False,
    ),
]


def copy_fixture(tmp_path, name=TAHOE) -> pathlib.Path:
    """Copy a fixture so tests can't change the checked-in file"""
    path = tmp_path / "NoteStore.sqlite"
    shutil.copy(DATA / name, path)
    return path


@pytest.fixture
def open_db():
    """Open NotesDatabases that are closed after the test"""
    opened = []

    def open_(path):
        opened.append(NotesDatabase(path))
        return opened[-1]

    yield open_
    for db in opened:
        db.close()


@pytest.fixture
def tahoe(tmp_path, open_db) -> NotesDatabase:
    return open_db(copy_fixture(tmp_path))


@pytest.fixture
def notes_app_writer(tmp_path):
    """A read-write connection standing in for Notes.app, and the database path"""
    path = copy_fixture(tmp_path)
    writer = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    writer.execute("PRAGMA journal_mode = WAL")
    yield writer, path
    writer.close()


def by_name(db: NotesDatabase) -> dict:
    return {r.name: r for r in db.notes()}


def utc(local: datetime) -> str:
    """Return a naive local datetime (as the database returns) in UTC, so tests
    don't depend on the time zone"""
    return local.astimezone(UTC).strftime("%Y-%m-%d %H:%M")


@pytest.mark.parametrize("fixture", FIXTURES, ids=str)
def test_fixture_notes(tmp_path, open_db, fixture):
    db = open_db(copy_fixture(tmp_path, fixture.file))
    [(account_id, account)] = db.accounts.items()
    assert account == "On My Mac"
    assert account_id.startswith("x-coredata://") and "/ICAccount/p" in account_id

    notes = by_name(db)
    plain = notes[fixture.plain]
    assert plain.folder == "Notes" and plain.folder_path == "Notes"
    assert not plain.password_protected
    assert plain.plaintext.startswith(f"{fixture.plain}\n")
    assert plain.creation_date <= plain.modification_date
    assert db.content_features(plain.id) == []
    assert all(r.account_id == account_id for r in notes.values())
    assert all(
        r.id.startswith(account_id.split("/ICAccount/")[0]) for r in notes.values()
    )
    buried = notes[fixture.buried]
    assert buried.folder == fixture.buried_path.split("/")[-1]
    assert buried.folder_path == fixture.buried_path
    # Notes.app lists notes in Recently Deleted, so the database does too
    assert any(r.folder == "Recently Deleted" for r in notes.values()) == (
        fixture.deleted
    )

    locked = notes[fixture.locked]
    assert locked.password_protected
    assert locked.plaintext == ""
    assert locked.tags == ()
    assert db.content_features(locked.id) == []
    assert [r.name for r in notes.values() if r.password_protected] == [fixture.locked]

    formatting = db.content_features(notes[fixture.formatted].id)
    assert fixture.formatting <= set(formatting)

    assert {name: r.tags for name, r in notes.items() if r.tags} == fixture.tags


@pytest.mark.parametrize("fixture", FIXTURES, ids=str)
def test_fixture_note_state(tmp_path, open_db, fixture):
    """The columns that Notes.app updates when it saves a change exist in every
    macOS version"""
    db = open_db(copy_fixture(tmp_path, fixture.file))
    note_id = by_name(db)[fixture.plain].id
    for change in CHANGE_COLUMNS:
        [value] = db.note_state(note_id, change)
        assert value is not None


def test_record_values(tahoe):
    """Values match what ScriptingBridge returns for the same notes"""
    notes = by_name(tahoe)
    note = notes["This is a note"]
    assert note.id == "x-coredata://9B3F80E8-BEEE-4921-BE3B-57B7D6FFAF2E/ICNote/p27"
    assert note.plaintext == "This is a note\n\nIt is not in a folder\n"
    assert utc(note.creation_date) == "2025-07-31 12:06"
    assert note.creation_date <= note.modification_date
    assert not note.password_protected
    assert notes["This note has tags"].tags == ("travel", "vacation")
    assert note.tags == ()


@pytest.mark.parametrize("tz", ["UTC", "America/Chicago", "Asia/Tokyo"])
def test_record_dates_any_time_zone(tmp_path, open_db, monkeypatch, tz):
    """Dates are local times, so the same instant in any time zone"""
    monkeypatch.setenv("TZ", tz)
    time.tzset()
    try:
        db = open_db(copy_fixture(tmp_path, MACOS27))
        note = by_name(db)["This is a plain text note"]
        assert utc(note.creation_date) == "2026-10-31 13:27"
        assert utc(note.modification_date) == "2026-10-31 13:27"
    finally:
        monkeypatch.undo()
        time.tzset()


@pytest.fixture
def macos27(tmp_path, open_db) -> NotesDatabase:
    return open_db(copy_fixture(tmp_path, MACOS27))


def test_macos27_record_values(macos27):
    notes = by_name(macos27)
    assert macos27.accounts == {
        "x-coredata://EB1BCA2E-7356-4972-8942-F674CA548E9C/ICAccount/p3": "On My Mac"
    }
    note = notes["This is a plain text note"]
    assert note.id == "x-coredata://EB1BCA2E-7356-4972-8942-F674CA548E9C/ICNote/p4"
    assert note.plaintext == (
        "This is a plain text note\n\nThis note has no special formatting\n"
    )
    assert not note.pinned
    # ScriptingBridge returns whole seconds
    assert note.creation_date.strftime("%S.%f") == "00.000000"
    assert note.modification_date.strftime("%S.%f") == "16.000000"
    assert sorted({r.folder_path for r in notes.values()}) == [
        "Folder1",
        "Folder2/SubFolder",
        "Folder2/SubFolder/SubSubFolder",
        "Notes",
    ]
    assert notes["This note is in a subfolder"].folder == "SubFolder"
    # a title with trailing whitespace
    checklist = notes["This note has a checklist with 1 item checked and 2 unchecked"]
    assert checklist.plaintext.splitlines()[2:] == ["Item 1", "Item 2", "Item 3"]


def test_macos27_filters(macos27):
    names = lambda records: sorted(r.name for r in records)  # noqa: E731
    assert names(macos27.notes(tag=["test"])) == [
        "This note has 2 tags: Test, todo",
        "This note has a tag named “Test”",
    ]
    assert names(macos27.notes(tag=["#TODO"])) == ["This note has 2 tags: Test, todo"]
    # the locked note's text isn't searched, but its title is
    assert names(macos27.notes(text=["foobar"])) == [
        "The locked note has password foobar",
        "This note is locked. The password is “foobar”",
    ]
    assert names(macos27.notes(body=["foobar"])) == [
        "The locked note has password foobar"
    ]
    assert names(macos27.notes(name=["named “test”"])) == [
        "This note has a tag named “Test”"
    ]
    assert macos27.notes(name=['named "test"']) == []
    assert names(macos27.notes(text=["goldfish.jpeg"])) == [
        "This note contains an image"
    ]


def test_macos27_content_features(macos27):
    """Each note in the macOS 27 fixture describes its own content"""
    features = {
        r.name: macos27.content_features(r.id)
        for r in macos27.notes(password_protected=False)
    }
    assert features == {
        "This is a plain text note": [],
        "This note has a tag named “Test”": ["tags"],
        "This note has a checklist with 1 item checked and 2 unchecked": ["checklists"],
        # the purple text is a highlight color
        "This note has text formatting": [
            "block quotes",
            "bold or italic",
            "headings",
            "highlights",
            "lists",
            "monospaced",
            "underline or strikethrough",
        ],
        "This note has 2 tags: Test, todo": ["tags"],
        "The locked note has password foobar": [],
        "This note contains an image": ["attachments"],
        "This note is in Folder1": [],
        "This note is in a subfolder": [],
        "This note is 3 levels deep in a folder": [],
    }


def test_relative_path(tmp_path, open_db, monkeypatch):
    copy_fixture(tmp_path, MACOS27)
    monkeypatch.chdir(tmp_path)
    db = open_db("NoteStore.sqlite")
    assert db.path == tmp_path / "NoteStore.sqlite"
    assert len(db.notes()) == 11
    connect_read_only(pathlib.Path("NoteStore.sqlite")).close()


def test_filters(tahoe):
    names = lambda records: sorted(r.name for r in records)  # noqa: E731
    # contains[cd]: case and diacritic insensitive
    assert names(tahoe.notes(name=["BURÍED"])) == ["This is a deeply buried note"]
    # ==[c]: case insensitive, but diacritics must match
    assert names(tahoe.notes(name=["THIS IS A NOTE"], exact_name=True)) == [
        "This is a note"
    ]
    assert tahoe.notes(name=["This is a nöte"], exact_name=True) == []
    assert tahoe.notes(name=["This is a"], exact_name=True) == []
    # values within a filter are OR'd; filters are AND'd
    assert len(tahoe.notes(name=["buried", "subfolder"])) == 2
    assert names(tahoe.notes(name=["note"], body=["Folder2"])) == [
        "This is a deeply buried note",
        "This is a note in a subfolder",
    ]
    assert names(tahoe.notes(text=["not in a folder"])) == ["This is a note"]
    assert names(tahoe.notes(password_protected=True)) == [
        "This note is password protected"
    ]
    # the text of locked notes is never searched
    assert tahoe.notes(text=["password"], password_protected=True)[0].plaintext == ""
    note = tahoe.notes(name=["This is a note"], exact_name=True)[0]
    assert tahoe.notes(id=[note.id]) == [note]
    assert tahoe.note(note.id) == note
    assert tahoe.note(note.id.replace("p27", "p999")) is None
    [account_id] = tahoe.accounts
    assert len(tahoe.notes(account_ids=[account_id])) == len(tahoe.notes())
    assert tahoe.notes(account_ids=["x-coredata://other/ICAccount/p1"]) == []


def test_tag_filter(tahoe):
    for tag in ["travel", "#Travel", "VACATION"]:
        assert [r.name for r in tahoe.notes(tag=[tag])] == ["This note has tags"]
    assert tahoe.notes(tag=["trav"]) == []


def test_content_features_unknown_note(tahoe):
    with pytest.raises(ValueError):
        tahoe.content_features("x-coredata://A/ICNote/p999")
    with pytest.raises(ValueError):
        tahoe.content_features("x-coredata://A/IMAPNote/p1")


def test_reads_do_not_change_database(tmp_path):
    path = copy_fixture(tmp_path)
    before = path.read_bytes()
    db = NotesDatabase(path)
    db.notes()
    db.close()
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["NoteStore.sqlite"]


def test_reloads_after_notes_app_writes(notes_app_writer, open_db):
    writer, path = notes_app_writer
    db = open_db(path)
    assert "Renamed" not in by_name(db)
    writer.execute(
        "UPDATE ZICCLOUDSYNCINGOBJECT SET ZTITLE1 = 'Renamed' WHERE Z_PK = 27"
    )
    assert by_name(db)["Renamed"].id.endswith("/p27")


def test_waits_for_pending_write(notes_app_writer, open_db):
    """After notify_write, the next read waits for Notes.app to save the change"""
    writer, path = notes_app_writer
    db = open_db(path)
    db.notes()

    def save_later():
        time.sleep(0.2)
        writer.execute(
            "UPDATE ZICCLOUDSYNCINGOBJECT SET ZTITLE1 = 'Saved' WHERE Z_PK = 27"
        )

    thread = threading.Thread(target=save_later)
    thread.start()
    db.notify_write()
    try:
        assert "Saved" in by_name(db)
    finally:
        thread.join()


def test_wait_is_for_save_after_write(notes_app_writer, open_db):
    """A save that happened before notify_write doesn't end the wait"""
    writer, path = notes_app_writer
    db = open_db(path)
    db.notes()
    writer.execute(
        "UPDATE ZICCLOUDSYNCINGOBJECT SET ZTITLE1 = 'Earlier' WHERE Z_PK = 27"
    )
    db.notify_write()

    def save_later():
        time.sleep(0.2)
        writer.execute(
            "UPDATE ZICCLOUDSYNCINGOBJECT SET ZTITLE1 = 'Later' WHERE Z_PK = 27"
        )

    thread = threading.Thread(target=save_later)
    thread.start()
    try:
        assert "Later" in by_name(db)
    finally:
        thread.join()


def test_unsaved_until_notes_app_saves(notes_app_writer, open_db):
    """A change is unsaved until its column changes, not when anything else is saved"""
    writer, path = notes_app_writer
    db = open_db(path)
    note_id = by_name(db)["This is a note"].id
    db.notify_write(note_id, "folder", db.note_state(note_id, "folder"))
    assert db.unsaved_note_ids() == {note_id}
    # Notes.app saves other changes first: another note, and this note's date
    writer.execute("UPDATE ZICCLOUDSYNCINGOBJECT SET ZTITLE1 = 'Other' WHERE Z_PK = 14")
    writer.execute(
        "UPDATE ZICCLOUDSYNCINGOBJECT SET ZMODIFICATIONDATE1 = 1 WHERE Z_PK = 27"
    )
    assert db.unsaved_note_ids() == {note_id}
    writer.execute("UPDATE ZICCLOUDSYNCINGOBJECT SET ZFOLDER = 1 WHERE Z_PK = 27")
    assert db.unsaved_note_ids() == set()
    assert db.note(note_id).folder == "Recently Deleted"


def test_new_note_unsaved_until_saved(notes_app_writer, open_db):
    writer, path = notes_app_writer
    db = open_db(path)
    new_id = by_name(db)["This is a note"].id.replace("/p27", "/p999")
    assert db.note_state(new_id, "modified") is None
    db.notify_write(new_id, "modified", None)
    assert db.unsaved_note_ids() == {new_id}
    writer.execute(
        "INSERT INTO ZICCLOUDSYNCINGOBJECT (Z_PK, Z_ENT, ZTITLE1) VALUES (999, 0, 'n')"
    )
    assert db.unsaved_note_ids() == set()


def test_unsaved_changes_expire_and_transfer(tahoe, tmp_path, open_db, monkeypatch):
    note_id = by_name(tahoe)["This is a note"].id
    before = tahoe.note_state(note_id, "title")
    tahoe.notify_write(note_id, "title", before, changed_at=time.time() - 30)
    [change] = tahoe.unsaved_changes()
    assert change[:3] == (note_id, "title", before)

    # another process (another NotesDatabase) can be told about the change
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other = open_db(copy_fixture(other_dir))
    other.notify_write(*change)
    assert other.unsaved_note_ids() == {note_id}

    monkeypatch.setattr(database, "UNSAVED_MAX_AGE_SECONDS", 10)
    assert tahoe.unsaved_note_ids() == set()


def test_pending_write_wait_is_bounded(tahoe, monkeypatch):
    monkeypatch.setattr(database, "WRITE_WAIT_SECONDS", 0.1)
    tahoe.notes()
    tahoe.notify_write()
    start = time.monotonic()
    assert tahoe.notes()
    assert time.monotonic() - start < 1


def test_connect_read_only_live_database(notes_app_writer):
    """With the -shm file present (Notes.app running), the database opens with mode=ro"""
    writer, path = notes_app_writer
    connection = connect_read_only(path)
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("UPDATE ZICCLOUDSYNCINGOBJECT SET ZTITLE1 = 'x'")
    connection.close()


def test_connect_refuses_unsaved_wal_without_shm(notes_app_writer, tmp_path):
    """Opening as immutable would ignore data in the -wal file, so that's an error"""
    writer, path = notes_app_writer
    writer.execute("PRAGMA wal_autocheckpoint = 0")
    writer.execute("UPDATE ZICCLOUDSYNCINGOBJECT SET ZTITLE1 = 'x' WHERE Z_PK = 27")
    copy = tmp_path / "copy"
    copy.mkdir()
    shutil.copy(path, copy / path.name)
    shutil.copy(f"{path}-wal", copy / f"{path.name}-wal")
    with pytest.raises(DatabaseUnavailableError):
        connect_read_only(copy / path.name)


def test_connect_missing(tmp_path):
    with pytest.raises(DatabaseUnavailableError):
        NotesDatabase(tmp_path / "missing.sqlite")


def test_connect_not_a_notes_database(tmp_path):
    path = tmp_path / "other.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE t (x)")
    connection.commit()
    connection.close()
    with pytest.raises(DatabaseUnavailableError):
        NotesDatabase(path)


def zdata(*runs) -> bytes:
    """Return ZDATA for a note with the given attribute runs, as dicts of fields"""
    proto = NoteStoreProto()
    proto.document.version = 1
    note = proto.document.note
    # one line per run; the first line is the title
    note.note_text = "x\n" * len(runs)
    for fields in runs:
        run = note.attribute_run.add()
        run.length = 1
        for key, value in fields.items():
            target = run
            *parents, leaf = key.split(".")
            for parent in parents:
                target = getattr(target, parent)
            setattr(target, leaf, value)
    return gzip.compress(proto.SerializeToString())


@pytest.mark.parametrize(
    "run, feature",
    [
        ({"paragraph_style.style_type": 1}, "headings"),
        ({"paragraph_style.style_type": 4}, "monospaced"),
        ({"paragraph_style.style_type": 102}, "lists"),
        ({"paragraph_style.style_type": 103}, "checklists"),
        (
            {
                "paragraph_style.checklist.uuid": b"x",
                "paragraph_style.checklist.done": 1,
            },
            "checklists",
        ),
        ({"paragraph_style.alignment": 1}, "alignment"),
        ({"paragraph_style.indent_amount": 1}, "indentation"),
        ({"paragraph_style.block_quote": 1}, "block quotes"),
        ({"font_weight": 1}, "bold or italic"),
        ({"underlined": 1}, "underline or strikethrough"),
        ({"strikethrough": 1}, "underline or strikethrough"),
        ({"superscript": -1}, "superscript or subscript"),
        ({"font.point_size": 20}, "fonts"),
        ({"font.font_name": "Menlo"}, "fonts"),
        (
            {"color.red": 1, "color.green": 0, "color.blue": 0, "color.alpha": 1},
            "colors",
        ),
        ({"emphasis_style": 1}, "highlights"),
        ({"link": "https://example.com"}, "links"),
        ({"attachment_info.type_uti": "public.jpeg"}, "attachments"),
        ({"attachment_info.type_uti": "public.url"}, "link previews"),
        ({"attachment_info.type_uti": "com.apple.notes.table"}, "tables"),
        (
            {
                "attachment_info.type_uti": "com.apple.notes.inlinetextattachment.hashtag"
            },
            "tags",
        ),
        (
            {"attachment_info.type_uti": "com.apple.notes.inlinetextattachment.x"},
            "inline objects",
        ),
    ],
)
def test_note_data_features(run, feature):
    assert note_data_features(zdata({"paragraph_style.style_type": 0}, run)) == [
        feature
    ]


def test_note_data_features_ignores_title_line():
    """A bold, large-font first line (a title created from HTML) isn't formatting"""
    title = {"font_weight": 1, "font.point_size": 24, "font.font_name": "Bold"}
    proto = NoteStoreProto()
    proto.document.version = 1
    note = proto.document.note
    note.note_text = "Tïtle 😀\nbody\n"
    # run lengths are UTF-16 code units: the emoji is 2
    for fields, length in [(title, 9), ({}, 5), ({"font_weight": 1}, 1)]:
        run = note.attribute_run.add()
        run.length = length
        if "font_weight" in fields:
            run.font_weight = fields["font_weight"]
        if "font.point_size" in fields:
            run.font.point_size = fields["font.point_size"]
            run.font.font_name = fields["font.font_name"]
    zdata = gzip.compress(proto.SerializeToString())
    assert note_data_features(zdata) == ["bold or italic"]
    del note.attribute_run[2]
    assert note_data_features(gzip.compress(proto.SerializeToString())) == []


def test_note_data_features_title_style():
    """The Title style is a heading in the body, but not on the title line"""

    def features(*runs):
        proto = NoteStoreProto()
        proto.document.version = 1
        note = proto.document.note
        note.note_text = "".join(text for text, _ in runs)
        for text, style_type in runs:
            run = note.attribute_run.add()
            run.length = len(text)
            if style_type is not None:
                run.paragraph_style.style_type = style_type
        return note_data_features(gzip.compress(proto.SerializeToString()))

    assert features(("Title\n", 0), ("body\n", None)) == []
    assert features(("Title", 0), ("\n", 0), ("body\n", None)) == []
    assert features(("Title\n", 0), ("body\n", None), ("Big\n", 0)) == ["headings"]
    assert features(("Title\nBig\n", 0)) == ["headings"]


def test_note_data_features_plain():
    assert note_data_features(zdata({"paragraph_style.style_type": 0}, {})) == []
    # indented list items are nested lists, not indentation
    nested = {"paragraph_style.style_type": 100, "paragraph_style.indent_amount": 1}
    assert note_data_features(zdata(nested)) == ["lists"]
    # locked notes are encrypted
    assert note_data_features(b"bplist00...") == []
    assert note_data_features(None) == []
