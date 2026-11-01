"""Fixtures for integration tests: everything happens in temporary folders"""

import gzip
import pathlib
import struct
import time
import uuid
import zlib

import pytest

from macnotesapp import Account, NotesApp, check_automation_permission
from macnotesapp.database import NoteRecord, NotesDatabase
from macnotesapp.errors import DatabaseUnavailableError
from macnotesapp.notesapp import FolderTree

# how long to wait for Notes.app to save a change to its database (#86)
SAVE_TIMEOUT_SECONDS = 60

# Notes.app sometimes puts a deleted folder back about 30 s later, so after the tests
# sweep_folders watches for this long
SWEEP_SECONDS = 40

NOTES_CONTAINER = pathlib.Path.home() / "Library/Group Containers/group.com.apple.notes"

# Every folder tests make, including subfolders, has a name starting with this.
TEST_FOLDER_PREFIX = "macnotesapp-test-"

# part of both backends' run IDs, so the sweep of earlier runs' folders spares this
# session's folders
SESSION_ID = uuid.uuid4().hex[:8]


@pytest.fixture(scope="session", params=["database", "scriptingbridge"])
def backend(request) -> str:
    """Run every test reading notes from the Notes database and from ScriptingBridge"""
    if request.param == "database":
        try:
            NotesDatabase().close()
        except DatabaseUnavailableError as e:
            pytest.skip(f"Notes database not readable: {e}")
    return request.param


@pytest.fixture(scope="session", autouse=True)
def unsaved_changes_file(tmp_path_factory):
    """Keep the CLI's record of unsaved changes out of the user's state directory"""
    from macnotesapp.cli import cli

    original = cli.UNSAVED_CHANGES_FILE
    cli.UNSAVED_CHANGES_FILE = tmp_path_factory.mktemp("state") / "unsaved.json"
    yield
    cli.UNSAVED_CHANGES_FILE = original


@pytest.fixture(scope="session")
def notesapp(backend) -> NotesApp:
    check_automation_permission()
    return NotesApp(backend=backend)


def earlier_test_folders(tree: FolderTree) -> list[str]:
    """Return IDs of top-level folders left by earlier test sessions.

    Subfolders count when Notes.app has left them at the top level after deleting
    their parent.
    """
    return [
        folder_id
        for folder_id in tree.children(None)
        if tree.names[folder_id].startswith(TEST_FOLDER_PREFIX)
        and SESSION_ID not in tree.names[folder_id]
    ]


@pytest.fixture(scope="session")
def sweep_earlier_folders():
    """Before the tests, delete folders left by earlier test sessions.

    Notes.app sometimes puts deleted folders back long after sweep_folders has
    finished (#89).
    """
    check_automation_permission()
    account = NotesApp(backend="scriptingbridge").account()
    tree = FolderTree.for_account(account.name)
    for folder_id in earlier_test_folders(tree):
        account._delete_folder_in_tree(tree, folder_id)


@pytest.fixture(scope="session")
def account(notesapp, sweep_earlier_folders) -> Account:
    """Default account; temporary folders are created here"""
    return notesapp.account()


@pytest.fixture(scope="session")
def run_id(backend) -> str:
    """Unique ID for this test run and backend, used in folder and note names.

    Each backend gets its own folders and notes: pytest may set up both backends'
    fixtures at the same time, and Notes allows two folders with the same name.
    """
    return f"{SESSION_ID}-{'db' if backend == 'database' else 'sb'}"


@pytest.fixture(scope="session", autouse=True)
def sweep_folders(account, run_id):
    """After the session, delete any folder left over from this run.

    Notes.app sometimes ignores a request to delete a folder, and leaves subfolders
    behind when deleting their parent, so folders made by tests have run_id in
    their names.
    """
    yield
    deadline = time.monotonic() + SWEEP_SECONDS
    while True:
        tree = FolderTree.for_account(account.name)
        leftovers = [i for i in tree.names if run_id in tree.names[i]]
        # delete top-level leftovers; delete_folder deletes their subfolders
        for folder_id in leftovers:
            if tree.parents.get(folder_id) not in leftovers:
                account.delete_folder(tree.path(folder_id))
        if time.monotonic() > deadline:
            break
        time.sleep(2)
    remaining = [n for n in FolderTree.for_account(account.name).paths() if run_id in n]
    assert not remaining, f"test folders not deleted: {remaining}"


def _temp_folder(account: Account, name: str):
    account.make_folder(name)
    try:
        yield name
    finally:
        # deleting a folder moves its notes to Recently Deleted
        if name in account.folders:
            account.delete_folder(name)


@pytest.fixture(scope="session")
def sandbox(account, run_id):
    """Name of a temporary folder that is deleted at the end of the session"""
    yield from _temp_folder(account, f"macnotesapp-test-{run_id}")


@pytest.fixture(scope="session")
def sandbox2(account, run_id):
    """Second temporary folder, used as a destination for moves"""
    yield from _temp_folder(account, f"macnotesapp-test-{run_id}-2")


@pytest.fixture
def note_name(run_id, request) -> str:
    """Unique note name for a test.

    Kept short: Notes truncates names of more than about 67 characters with "…".
    """
    return f"macnotesapp test {run_id} {request.node.originalname}"


def wait_until_saved(note_id: str, timeout: float = SAVE_TIMEOUT_SECONDS) -> NoteRecord:
    """Wait for Notes.app to save a new note to its database and return it.

    Skips the test if the database isn't readable or Notes.app doesn't save in time.
    """
    try:
        database = NotesDatabase()
    except DatabaseUnavailableError as e:
        pytest.skip(f"Notes database not readable: {e}")
    try:
        deadline = time.monotonic() + timeout
        while (record := database.note(note_id)) is None:
            if time.monotonic() > deadline:
                pytest.skip(f"Notes.app didn't save the note in {timeout} s (#86)")
            time.sleep(0.5)
        return record
    finally:
        database.close()


def saved_attachments(
    note_id: str, count: int, timeout: float = SAVE_TIMEOUT_SECONDS
) -> tuple[list[str], list[str], list[str]]:
    """Wait for Notes.app to save count attachments of a note to its database.

    Skips the test if Notes.app doesn't save the attachments in time. If it saves
    them but not their files, returns anyway, so the test's assertions fail.

    Returns:
        type UTIs of the note's attachments; of the attachments its text refers
        to (an attachment Notes.app shows twice is referred to twice); and of the
        attachments whose file Notes.app stored. Notes.app makes attachments without
        a file from HTML that points to a file.
    """
    from apple_notes_parser.notestore_pb2 import NoteStoreProto

    from macnotesapp.database import _primary_key

    try:
        database = NotesDatabase()
    except DatabaseUnavailableError as e:
        pytest.skip(f"Notes database not readable: {e}")
    connection = database._connection
    pk = _primary_key(note_id)
    deadline = time.monotonic() + timeout
    try:
        while True:
            rows = connection.execute(
                "SELECT a.ZTYPEUTI, m.ZIDENTIFIER FROM ZICCLOUDSYNCINGOBJECT a "
                "LEFT JOIN ZICCLOUDSYNCINGOBJECT m ON a.ZMEDIA = m.Z_PK "
                "WHERE a.ZNOTE = ? AND a.ZTYPEUTI IS NOT NULL "
                "AND a.ZMARKEDFORDELETION = 0",
                (pk,),
            ).fetchall()
            attachments = [uti for uti, _ in rows]
            stored = [
                uti
                for uti, media_id in rows
                if media_id
                and any(
                    p.is_file()
                    for p in NOTES_CONTAINER.glob(f"Accounts/*/Media/{media_id}/**/*")
                )
            ]
            row = connection.execute(
                "SELECT ZDATA FROM ZICNOTEDATA WHERE ZNOTE = ?", (pk,)
            ).fetchone()
            references = []
            if row and row[0]:
                proto = NoteStoreProto()
                proto.ParseFromString(gzip.decompress(row[0]))
                references = [
                    run.attachment_info.type_uti
                    for run in proto.document.note.attribute_run
                    if run.HasField("attachment_info")
                ]
            saved = len(attachments) >= count and len(references) >= count
            if saved and len(stored) >= count:
                return sorted(attachments), sorted(references), sorted(stored)
            if time.monotonic() > deadline:
                if saved:
                    return sorted(attachments), sorted(references), sorted(stored)
                pytest.skip(
                    f"Notes.app didn't save the attachments in {timeout} s (#86)"
                )
            time.sleep(0.5)
    finally:
        database.close()


def png_file(path):
    """Write a small PNG image to path and return path"""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\x00" + b"\xff\x00\x00" * 8 for _ in range(8))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    return path
