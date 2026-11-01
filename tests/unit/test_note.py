"""Test Note and NotesList using fake ScriptingBridge objects"""

import pathlib
import shutil
from datetime import datetime

import applescript
import Foundation
import pytest

import macnotesapp.notesapp as notesapp
from macnotesapp.database import NoteRecord, NotesDatabase
from macnotesapp.errors import (
    AppleScriptError,
    ContentLossError,
    DatabaseUnavailableError,
    FolderNotFoundError,
    MacNotesAppError,
)
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


# ---- writing notes (Phase 3)


class FakeSBAttachment:
    def __init__(self, id_):
        self._id = id_

    def id(self):
        return self._id

    def name(self):
        return f"name of {self._id}"


class FakeSBAttachments(list):
    def objectWithID_(self, id_):
        # like ScriptingBridge, return a reference even if there's no such object
        return next((a for a in self if a.id() == id_), FakeSBAttachment(id_))


def _writable_note(database=None, record=None, normalize=True):
    """A note whose body can be set; Notes.app rewrites HTML, so set bodies get a
    trailing newline unless normalize is False."""
    sbnote = FakeSBNote(
        id="x-coredata://A/ICNote/p1",
        name="record1",
        body="<div><h1>record1</h1></div>\n<div>old</div>\n",
        passwordProtected=False,
    )
    attachments = FakeSBAttachments()
    sbnote.attachments = lambda: attachments
    sbnote.set_count = 0

    def set_value(value, key):
        sbnote.set_count += 1
        sbnote._props[key] = f"{value}\n" if normalize else sbnote._props[key]

    sbnote.setValue_forKey_ = set_value
    database = database if database is not None else FakeDatabase([_record(1)])
    note = Note(sbnote, account="iCloud", record=record, database=database)
    return note, sbnote


def test_append(no_applescript):
    """#51: append adds to the end of the note's HTML"""
    note, sbnote = _writable_note()
    note.append("new <line>\nsecond")
    assert sbnote.body() == (
        "<div><h1>record1</h1></div>\n<div>old</div>\n"
        "<div>new &lt;line&gt;</div>\n<div>second</div>\n\n"
    )
    # set once, with ScriptingBridge
    assert sbnote.set_count == 1
    assert note._database.writes == [
        (note.id, "modified", ("state", note.id, "modified"))
    ]


def test_append_markdown(no_applescript):
    note, sbnote = _writable_note()
    note.append("- item", format="markdown")
    assert "<li>item</li>" in sbnote.body()


@pytest.mark.parametrize("features", [["checklists"], ["attachments", "tags"]])
def test_append_refuses_content_loss(no_applescript, features):
    """#51, #71: appending refuses to lose content unless forced"""
    record = _record(1)
    database = FakeDatabase([record], features={record.id: features})
    note, sbnote = _writable_note(database)
    with pytest.raises(ContentLossError) as e:
        note.append("x")
    assert e.value.features == features
    assert sbnote.set_count == 0
    note.append("x", force=True)
    assert sbnote.set_count == 1


def test_append_keeps_safe_content(no_applescript):
    record = _record(1)
    features = {record.id: ["bold or italic", "lists", "tables", "dividers"]}
    note, sbnote = _writable_note(FakeDatabase([record], features=features))
    note.append("x")
    assert sbnote.set_count == 1


def test_append_without_database_needs_force(no_applescript):
    """Without the database, content can't be checked, so append refuses"""
    note, sbnote = _writable_note(database=None)
    note._database = None
    with pytest.raises(ContentLossError, match="Can't check"):
        note.append("x")
    note.append("x", force=True)
    assert sbnote.set_count == 1


def test_append_locked(no_applescript):
    note, sbnote = _writable_note()
    sbnote._props["passwordProtected"] = True
    with pytest.raises(MacNotesAppError, match="locked"):
        note.append("x", force=True)


def test_append_unknown_format(no_applescript):
    note, _ = _writable_note()
    with pytest.raises(ValueError):
        note.append("x", format="rtf")


def test_content_features_waits_for_save(monkeypatch):
    """The database has old content until Notes.app saves a change"""
    monkeypatch.setattr(notesapp, "CONTENT_SAVE_WAIT_SECONDS", 0.05)
    record = _record(1)
    database = FakeDatabase([record], features={record.id: ["tables"]})
    note = Note(
        FakeSBNote(id=record.id, name="new name"), account="iCloud", database=database
    )
    database.unsaved = {record.id}
    with pytest.raises(DatabaseUnavailableError, match="hasn't saved"):
        note.content_features()
    # a new note isn't in the database until it's saved
    database.unsaved = set()
    database.records = []
    with pytest.raises(DatabaseUnavailableError):
        note.content_features()
    database.records = [record]
    assert note.content_features() == ["tables"]


def test_body_setter_uses_applescript_only_if_needed(monkeypatch):
    """Setting the body twice would add attachments in it twice"""
    calls = []
    monkeypatch.setattr(notesapp, "run_script", lambda *args: calls.append(args))
    note, sbnote = _writable_note()
    note.body = "<div>new</div>"
    assert calls == []
    # ScriptingBridge didn't change the body, so use AppleScript
    note, sbnote = _writable_note(normalize=False)
    note.body = "<div>new</div>"
    assert calls == [("noteSetBody", "iCloud", note.id, "<div>new</div>")]


def test_add_attachment_uses_applescript(monkeypatch, tmp_path):
    """#64: attachments are added with AppleScript, which copies the file into the
    note; HTML pointing at the file makes an attachment without its contents"""
    path = tmp_path / "file.txt"
    path.write_text("x")
    note, sbnote = _writable_note()
    calls = []

    def run_script(*args):
        calls.append(args)
        sbnote.attachments().append(FakeSBAttachment("att-as"))
        return "att-as"

    monkeypatch.setattr(notesapp, "run_script", run_script)
    attachment = note.add_attachment(path)
    assert attachment.id == "att-as"
    assert calls == [("noteAddAttachment", "iCloud", note.id, str(path.resolve()))]
    assert sbnote.set_count == 0


def test_add_attachment_id_from_error(monkeypatch, tmp_path):
    """Notes.app can't find some attachments it just made, such as PDFs, but the
    error has the ID"""
    path = tmp_path / "file.pdf"
    path.write_text("x")
    note, sbnote = _writable_note()
    sbnote.attachments().append(FakeSBAttachment("x-coredata://A/ICAttachment/p5"))

    def run_script(*args):
        raise applescript.ScriptError(
            {
                "NSAppleScriptErrorMessage": "Can't get attachment id "
                '"x-coredata://A/ICAttachment/p5".'
            }
        )

    monkeypatch.setattr(notesapp, "run_script", run_script)
    assert note.add_attachment(path).id == "x-coredata://A/ICAttachment/p5"


def test_add_attachment_missing_file(no_applescript, tmp_path):
    note, _ = _writable_note()
    with pytest.raises(FileNotFoundError):
        note.add_attachment(tmp_path / "missing.txt")


class FakeNoteClass:
    """Stand-in for the class ScriptingBridge makes notes with"""

    def __init__(self):
        self.properties = None

    def alloc(self):
        return self

    def initWithProperties_(self, properties):
        self.properties = properties
        self.note = FakeSBNote(id="x-coredata://A/ICNote/p9")
        attachments = FakeSBAttachments()
        self.note.attachments = lambda: attachments
        return self.note


class FakeSBNotesToAdd(list):
    def addObject_(self, note):
        self.append(note)


class FakeSBFolders(list):
    """An account's folders as ScriptingBridge returns them"""

    def filteredArrayUsingPredicate_(self, predicate):
        # only predicates like 'name == "Work"' are used
        field, _, value = str(predicate.predicateFormat()).partition(" == ")
        return [f for f in self if getattr(f, field)() == value.strip('"')]

    def objectWithID_(self, folder_id):
        return next(f for f in self if f.id() == folder_id)

    def arrayByApplyingSelector_(self, selector):
        return [getattr(f, selector)() for f in self]


class FakeSBFolder:
    def __init__(self, folder_id, name):
        self._id, self._name = folder_id, name
        self._notes = FakeSBNotesToAdd()

    def id(self):
        return self._id

    def name(self):
        return self._name

    def notes(self):
        return self._notes


class FakeFolderStore:
    """Folders of a fake account, answering the folder AppleScript handlers"""

    def __init__(self, *folders, ignore_deletes=0):
        # (id, name, parent id)
        self.folders = list(folders)
        self.calls = []
        self.ignore_deletes = ignore_deletes
        # folder id: how many times Notes.app puts it back after it's deleted
        self.put_back = {}
        self._put_back_pending = []

    def run_script(self, handler, *args):
        self.calls.append((handler, *args))
        if handler == "accountGetFolderTree":
            return [[f[i] for f in self.folders] for i in range(3)] or [[], [], []]
        if handler in ("folderCreate", "folderCreateIn"):
            parent = args[1] if handler == "folderCreateIn" else ""
            folder_id = f"new{len(self.folders)}"
            self.folders.append((folder_id, args[-1], parent))
            return folder_id
        if handler == "folderDelete":
            if self.ignore_deletes:
                self.ignore_deletes -= 1
                return None
            deleted = [f for f in self.folders if f[0] == args[1]]
            self.folders = [f for f in self.folders if f[0] != args[1]]
            for folder in deleted:
                if self.put_back.get(folder[0]):
                    self.put_back[folder[0]] -= 1
                    # put back after the next listing, as Notes.app does later
                    self._put_back_pending.append([folder, 1])
            return None
        if handler == "noteMoveToFolder":
            return None
        if handler == "noteAddAttachment":
            return f"att{len([c for c in self.calls if c[0] == handler])}"
        raise AssertionError(f"unexpected AppleScript {handler}")

    def sb_account(self):
        store = self

        class SBAccount:
            def folders(self):
                for pending in list(store._put_back_pending):
                    if pending[1] == 0:
                        store.folders.append(pending[0])
                        store._put_back_pending.remove(pending)
                    else:
                        pending[1] -= 1
                return FakeSBFolders(FakeSBFolder(f[0], f[1]) for f in store.folders)

            def defaultFolder(self):
                return self.folders()[0]

        return SBAccount()


@pytest.fixture
def folder_store(monkeypatch):
    store = FakeFolderStore(
        ("notes", "Notes", ""),
        ("work", "Work", ""),
        ("projects", "Projects", "work"),
        ("2026", "2026", "projects"),
    )
    monkeypatch.setattr(notesapp, "run_script", store.run_script)
    return store


def test_make_note_formats_and_attachments(monkeypatch, folder_store, tmp_path):
    """#39, #64, #4: make_note converts the body, attaches files, and finds subfolders"""
    note_class = FakeNoteClass()
    app = type("App", (), {"classForScriptingClass_": lambda self, c: note_class})()
    monkeypatch.setattr(notesapp, "_notes_application", lambda: app)
    path = tmp_path / "a.txt"
    path.write_text("x")
    account = Account(folder_store.sb_account(), name="iCloud", id="acct")
    note = account.make_note(
        "Tom & Jerry",
        "**bold**",
        "Work/Projects",
        attachments=[path],
        format="markdown",
    )
    assert note.id == "x-coredata://A/ICNote/p9"
    body = note_class.properties["body"]
    assert body.startswith("<div><h1>Tom &amp; Jerry</h1></div>\n<p><strong>bold")
    assert "object" not in body
    # attachments are added after the note is made, with AppleScript
    assert folder_store.calls[-1] == (
        "noteAddAttachment",
        "iCloud",
        "x-coredata://A/ICNote/p9",
        str(path.resolve()),
    )


def test_make_note_missing_attachment_creates_nothing(
    monkeypatch, folder_store, tmp_path
):
    note_class = FakeNoteClass()
    app = type("App", (), {"classForScriptingClass_": lambda self, c: note_class})()
    monkeypatch.setattr(notesapp, "_notes_application", lambda: app)
    account = Account(folder_store.sb_account(), name="iCloud", id="acct")
    with pytest.raises(FileNotFoundError):
        account.make_note("n", "b", attachments=[tmp_path / "missing"])
    assert note_class.properties is None
    with pytest.raises(FolderNotFoundError):
        account.make_note("n", "b", "Work/Missing")
    assert note_class.properties is None


def test_move_to_subfolder(folder_store):
    """#4: notes can be moved into subfolders"""
    note = Note(FakeSBNote(id="x-coredata://A/IMAPNote/p1"), account="iCloud")
    note.move("Work/Projects/2026")
    assert folder_store.calls[-1] == (
        "noteMoveToFolder",
        "iCloud",
        "x-coredata://A/IMAPNote/p1",
        "2026",
    )
    with pytest.raises(FolderNotFoundError):
        note.move("Nowhere")


def test_make_folder(folder_store):
    """#4: folders can be made inside other folders"""
    account = Account(folder_store.sb_account(), name="iCloud", id="acct")
    account.make_folder("Archive")
    assert folder_store.calls[-1] == ("folderCreate", "iCloud", "Archive")
    folder = account.make_folder("Work/Projects/2027")
    assert folder_store.calls[-1] == ("folderCreateIn", "iCloud", "projects", "2027")
    assert folder.name == "2027"
    with pytest.raises(MacNotesAppError, match="already exists"):
        account.make_folder("Work/Projects")
    with pytest.raises(FolderNotFoundError):
        account.make_folder("New/Child")
    assert account.make_folder("Work/Projects", parents=True).id == "projects"
    account.make_folder("New/Child", parents=True)
    assert "New/Child" in account.folder_paths
    # a subfolder found by name doesn't count as an existing top-level folder
    account.make_folder("Projects")
    assert account.folder_paths.count("Projects") == 1


def test_delete_folder_deletes_subfolders_first(folder_store):
    """Notes.app leaves subfolders behind when deleting a folder"""
    account = Account(folder_store.sb_account(), name="iCloud", id="acct")
    account.delete_folder("Work")
    deletes = [c[2] for c in folder_store.calls if c[0] == "folderDelete"]
    assert deletes == ["2026", "projects", "work"]
    assert account.folder_paths == ["Notes"]


def test_delete_folder_retries(folder_store, monkeypatch):
    """Notes.app sometimes ignores a request to delete a folder"""
    monkeypatch.setattr(notesapp, "FOLDER_DELETE_WAIT_SECONDS", 0)
    account = Account(folder_store.sb_account(), name="iCloud", id="acct")
    folder_store.ignore_deletes = 1
    account.delete_folder("Notes")
    assert [c[0] for c in folder_store.calls].count("folderDelete") == 2
    folder_store.ignore_deletes = notesapp.FOLDER_DELETE_ATTEMPTS
    with pytest.raises(AppleScriptError, match="did not delete"):
        account.delete_folder("Work/Projects/2026")


def test_delete_folder_confirm(folder_store, monkeypatch):
    """Notes.app sometimes puts a deleted folder back, so confirm_seconds checks
    for a while and deletes it again"""
    monkeypatch.setattr(notesapp, "FOLDER_CONFIRM_INTERVAL_SECONDS", 0)
    account = Account(folder_store.sb_account(), name="iCloud", id="acct")
    folder_store.put_back = {"archive": 1}
    folder_store.folders.append(("archive", "Archive", ""))
    account.delete_folder("Archive", confirm_seconds=0.05)
    assert [c[0] for c in folder_store.calls].count("folderDelete") == 2
    assert "Archive" not in account.folder_paths

    folder_store.put_back = {"notes": 100}
    with pytest.raises(AppleScriptError, match="keeps putting back"):
        account.delete_folder("Notes", confirm_seconds=1)


def test_delete_folder_without_confirm_returns_at_once(folder_store, monkeypatch):
    monkeypatch.setattr(notesapp, "FOLDER_CONFIRM_INTERVAL_SECONDS", 10)
    account = Account(folder_store.sb_account(), name="iCloud", id="acct")
    folder_store.put_back = {"notes": 1}
    account.delete_folder("Notes")
    assert [c[0] for c in folder_store.calls].count("folderDelete") == 1


def test_make_folder_uses_full_paths(folder_store):
    """A subfolder with the same name doesn't stop making a top-level folder, and
    parents are found by their full paths"""
    folder_store.folders.append(("home", "Home", ""))
    folder_store.folders.append(("home-projects", "Projects", "home"))
    folder_store.folders.append(("home-work", "Work2", "home"))
    account = Account(folder_store.sb_account(), name="iCloud", id="acct")
    # two subfolders named Projects (Work/Projects, Home/Projects)
    account.make_folder("Projects")
    assert folder_store.calls[-1] == ("folderCreate", "iCloud", "Projects")
    # Home/Work2 exists, but Work2/New is made at the top level
    account.make_folder("Work2/New", parents=True)
    creates = [c for c in folder_store.calls if c[0].startswith("folderCreate")]
    assert creates[-2] == ("folderCreate", "iCloud", "Work2")
    assert "Work2/New" in account.folder_paths
    with pytest.raises(FolderNotFoundError):
        account.make_folder("Missing/New")


def test_folder_for_name_fast_path(folder_store):
    """A name that one folder has is found without the folder tree"""
    account = Account(folder_store.sb_account(), name="iCloud", id="acct")
    assert account.folder("2026").id == "2026"
    assert not folder_store.calls
    # two folders named Projects: the folder tree picks the top-level one
    folder_store.folders.append(("top-projects", "Projects", ""))
    assert account.folder("Projects").id == "top-projects"
    assert folder_store.calls == [("accountGetFolderTree", "iCloud")]


def test_body_setter_when_scriptingbridge_cant_read_body(monkeypatch):
    """When ScriptingBridge returns no body, it's read with AppleScript, so a body
    that ScriptingBridge did set isn't set again"""
    bodies = ["<div>old</div>"]
    calls = []

    def run_script(handler, *args):
        calls.append(handler)
        return bodies[-1]

    monkeypatch.setattr(notesapp, "run_script", run_script)
    note, sbnote = _writable_note()
    sbnote.body = lambda: None
    sbnote.setValue_forKey_ = lambda value, key: bodies.append(value)
    note.body = "<div>new</div>"
    assert calls == ["noteGetBody", "noteGetBody"]
