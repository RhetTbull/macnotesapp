"""Read notes directly from the Notes database (NoteStore.sqlite)

Reading the database is much faster than asking Notes.app through ScriptingBridge or
AppleScript, but needs permission to read Notes' data (Full Disk Access, or
"access data from other apps" on newer macOS). It only covers accounts that Notes keeps
in the database (iCloud and On My Mac, not IMAP accounts such as Google).
Writes always go through Notes.app.

Parsing is done by apple-notes-parser; this module opens the database read-only,
reloads it when Notes.app changes it, and filters notes the way ScriptingBridge does.

Notes.app saves changes to the database on its own schedule: a change made through
AppleScript or ScriptingBridge can take from under a second to more than 20 seconds to
appear, and Notes.app has no command to save sooner. NotesDatabase therefore tracks the
changes macnotesapp asked for (notify_write()) until they are saved, and NotesApp reads
those notes from Notes.app in the meantime (unsaved_note_ids()).
"""

from __future__ import annotations

import gzip
import os
import pathlib
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from .errors import DatabaseUnavailableError
from .logging import logger

DEFAULT_DATABASE_PATH = (
    pathlib.Path.home()
    / "Library"
    / "Group Containers"
    / "group.com.apple.notes"
    / "NoteStore.sqlite"
)

# what changes in the database when Notes.app saves each kind of change to a note
CHANGE_COLUMNS = {
    "folder": "ZFOLDER",  # move or delete (to Recently Deleted)
    "title": "ZTITLE1",  # rename
    "modified": "ZMODIFICATIONDATE1",  # body or attachments
}

# how long to wait for Notes.app to save a change to folders before reading the
# database again
WRITE_WAIT_SECONDS = 2.0

# stop treating a change as unsaved after this long, in case Notes.app never saves it
UNSAVED_MAX_AGE_SECONDS = 600

# paragraph styles in the note protobuf
STYLE_TITLE = 0
STYLE_HEADING = 1
STYLE_SUBHEADING = 2
STYLE_MONOSPACED = 4
STYLE_LISTS = (100, 101, 102)  # dotted, dashed, numbered
STYLE_CHECKLIST = 103

ATTACHMENT_FEATURES = {
    "com.apple.notes.table": "tables",
    "com.apple.notes.inlinetextattachment.hashtag": "tags",
    "com.apple.notes.inlinetextattachment.mention": "mentions",
    "public.url": "link previews",
}


@dataclass(frozen=True)
class NoteRecord:
    """A note as read from the database"""

    id: str
    name: str
    account: str
    account_id: str
    folder: str
    folder_path: str
    plaintext: str
    creation_date: datetime | None
    modification_date: datetime | None
    password_protected: bool
    pinned: bool
    tags: tuple[str, ...]


class NotesDatabase:
    """Read-only view of the Notes database that reloads when Notes.app changes it"""

    def __init__(self, path: str | os.PathLike | None = None):
        """Open the database read-only

        Args:
            path: path to NoteStore.sqlite; defaults to the current user's database

        Raises:
            DatabaseUnavailableError: if the database can't be opened
        """
        self.path = pathlib.Path(path).absolute() if path else DEFAULT_DATABASE_PATH
        self._connection = connect_read_only(self.path)
        self._data_version: int | None = None
        # changes to notes that Notes.app may not have saved yet:
        # (note ID, kind of change, note_state() before the change, time of change)
        self._unsaved: list[tuple[str, str, tuple | None, float]] = []
        # data version when Notes.app was asked to change folders
        self._folder_write_version: int | None = None
        self._records: list[NoteRecord] = []
        self._accounts: dict[str, str] = {}

    @property
    def accounts(self) -> dict[str, str]:
        """Return dict of account ID to account name for accounts in the database"""
        self._refresh()
        return dict(self._accounts)

    def notes(
        self,
        name: list[str] | None = None,
        body: list[str] | None = None,
        text: list[str] | None = None,
        password_protected: bool | None = None,
        id: list[str] | None = None,
        account_ids: list[str] | None = None,
        exact_name: bool = False,
        tag: list[str] | None = None,
    ) -> list[NoteRecord]:
        """Return notes matching all the given filters, like NotesApp.notes()

        Values within a filter are OR'd together. Text matches ignore case and
        diacritics; exact name and tag matches ignore case only, as in ScriptingBridge.
        """
        self._refresh()
        return filter_records(
            self._records,
            name=name,
            body=body,
            text=text,
            password_protected=password_protected,
            id=id,
            account_ids=account_ids,
            exact_name=exact_name,
            tag=tag,
        )

    def note(self, note_id: str) -> NoteRecord | None:
        """Return the note with ID note_id, or None if it isn't in the database"""
        notes = self.notes(id=[note_id])
        return notes[0] if notes else None

    def content_features(self, note_id: str) -> list[str]:
        """Return the kinds of content in a note besides plain text, such as
        "tables", "checklists", or "fonts"; see formatting.features_lost()

        Raises:
            ValueError: if the note isn't in the database
        """
        pk = _primary_key(note_id)
        row = self._connection.execute(
            "SELECT ZDATA FROM ZICNOTEDATA WHERE ZNOTE = ?", (pk,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Note {note_id} is not in the database")
        return note_data_features(row[0])

    def note_state(self, note_id: str, change: str) -> tuple | None:
        """Return the value that Notes.app updates when it saves a change to a note

        Args:
            note_id: the note's ID
            change: kind of change, a key of CHANGE_COLUMNS

        Returns:
            a 1-tuple with the value, or None if the note isn't in the database
        """
        column = CHANGE_COLUMNS[change]
        row = self._connection.execute(
            f"SELECT {column} FROM ZICCLOUDSYNCINGOBJECT WHERE Z_PK = ?",
            (_primary_key(note_id),),
        ).fetchone()
        return tuple(row) if row else None

    def notify_write(
        self,
        note_id: str | None = None,
        change: str | None = None,
        state_before: tuple | None = None,
        changed_at: float | None = None,
    ):
        """Note that Notes.app was asked to make a change.

        A change to a note counts as unsaved (see unsaved_note_ids()) until
        note_state(note_id, change) differs from state_before (None for a new note).
        Without note_id (a change to folders), the next read waits briefly for
        Notes.app to save anything.

        Args:
            note_id: ID of the changed note
            change: kind of change, a key of CHANGE_COLUMNS
            state_before: note_state(note_id, change) before the change
            changed_at: time.time() of the change; defaults to now
        """
        if note_id:
            self._unsaved.append(
                (note_id, change, state_before, changed_at or time.time())
            )
        else:
            self._folder_write_version = self._data_version_now()

    def unsaved_changes(self) -> list[tuple[str, str, tuple | None, float]]:
        """Return changes to notes that Notes.app hasn't saved yet, as arguments
        for notify_write(), for example to pass them to another process"""
        oldest = time.time() - UNSAVED_MAX_AGE_SECONDS
        self._unsaved = [
            (note_id, change, before, changed_at)
            for note_id, change, before, changed_at in self._unsaved
            if changed_at > oldest and self.note_state(note_id, change) == before
        ]
        return list(self._unsaved)

    def unsaved_note_ids(self) -> set[str]:
        """Return IDs of notes with changes that Notes.app hasn't saved yet;
        the database has old values for these notes"""
        return {change[0] for change in self.unsaved_changes()}

    def wait_for_writes(self):
        """Wait up to WRITE_WAIT_SECONDS for Notes.app to save changes to folders"""
        if self._folder_write_version is None:
            return
        deadline = time.monotonic() + WRITE_WAIT_SECONDS
        while (
            self._data_version_now() == self._folder_write_version
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)
        self._folder_write_version = None

    def close(self):
        """Close the database"""
        self._connection.close()

    def _refresh(self):
        """Reload the database if Notes.app has changed it since the last load"""
        self.wait_for_writes()
        version = self._data_version_now()
        if version != self._data_version:
            self._load()
            self._data_version = version

    def _data_version_now(self) -> int:
        return self._connection.execute("PRAGMA data_version").fetchone()[0]

    def _load(self):
        """Load accounts and notes; runs in one read transaction for a consistent view"""
        start = time.monotonic()
        self._connection.execute("BEGIN")
        try:
            accounts, records = _load_records(self.path, self._connection)
        finally:
            self._connection.execute("COMMIT")
        self._accounts = accounts
        self._records = records
        logger.debug(
            f"Loaded {len(records)} notes from {self.path} "
            f"in {time.monotonic() - start:.2f}s"
        )


def filter_records(
    records: list[NoteRecord],
    name: list[str] | None = None,
    body: list[str] | None = None,
    text: list[str] | None = None,
    password_protected: bool | None = None,
    id: list[str] | None = None,
    account_ids: list[str] | None = None,
    exact_name: bool = False,
    tag: list[str] | None = None,
) -> list[NoteRecord]:
    """Return records matching all the given filters; see NotesDatabase.notes()"""
    if account_ids is not None:
        account_ids = set(account_ids)
        records = [r for r in records if r.account_id in account_ids]
    if id:
        ids = set(id)
        records = [r for r in records if r.id in ids]
    if password_protected is not None:
        records = [r for r in records if r.password_protected == password_protected]
    if name:
        if exact_name:
            names = {n.casefold() for n in name}
            records = [r for r in records if r.name.casefold() in names]
        else:
            records = [r for r in records if _contains_any(r.name, name)]
    if tag:
        tags = {t.lstrip("#").casefold() for t in tag}
        records = [r for r in records if any(t.casefold() in tags for t in r.tags)]
    if body:
        records = [r for r in records if _contains_any(r.plaintext, body)]
    if text:
        records = [
            r
            for r in records
            if _contains_any(r.name, text) or _contains_any(r.plaintext, text)
        ]
    return list(records)


def connect_read_only(path: pathlib.Path) -> sqlite3.Connection:
    """Open a SQLite database read-only without changing it or creating files

    Notes keeps the database in WAL mode. A read-only connection to a WAL database uses
    the -shm file, which exists while Notes.app has the database open. Without it,
    SQLite would create -shm and -wal files next to the database, so instead the
    database is opened as immutable if there is no unsaved data in the -wal file.
    Opening as immutable while the -wal file holds data would silently return stale
    data, so that case is an error.

    Raises:
        DatabaseUnavailableError: if the database can't be opened
    """
    path = path.absolute()
    shm = path.with_name(f"{path.name}-shm")
    wal = path.with_name(f"{path.name}-wal")
    try:
        if not path.is_file():
            raise DatabaseUnavailableError(f"Notes database not found at {path}")
        if shm.exists():
            mode = "ro"
        elif wal.exists() and wal.stat().st_size:
            raise DatabaseUnavailableError(
                f"Can't read {path} safely: {wal.name} has unsaved changes "
                f"but {shm.name} is missing"
            )
        else:
            mode = "ro&immutable=1"
    except PermissionError as e:
        raise DatabaseUnavailableError(f"Not allowed to read {path}: {e}") from e
    try:
        return _connect(f"{path.as_uri()}?mode={mode}")
    except sqlite3.Error as e:
        raise DatabaseUnavailableError(f"Could not open {path}: {e}") from e


def _connect(uri: str) -> sqlite3.Connection:
    """Connect and run a query so permission and format errors show up now"""
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("SELECT Z_UUID FROM Z_METADATA").fetchone()
    except sqlite3.Error:
        connection.close()
        raise
    return connection


def _load_records(
    path: pathlib.Path, connection: sqlite3.Connection
) -> tuple[dict[str, str], list[NoteRecord]]:
    """Return accounts (ID to name) and notes read with apple-notes-parser"""
    # imported here: apple-notes-parser loads protobuf
    from apple_notes_parser.database import AppleNotesDatabase
    from apple_notes_parser.embedded_objects import EmbeddedObjectExtractor

    class Database(AppleNotesDatabase):
        """AppleNotesDatabase that uses our read-only connection"""

        def connect(self):
            self.connection = connection
            self.connection.row_factory = sqlite3.Row
            self._embedded_extractor = EmbeddedObjectExtractor(
                connection, self.get_macos_version()
            )

        def close(self):
            pass

    db = Database(str(path))
    z_uuid = db.get_z_uuid()
    # apple-notes-parser treats any row with a name as an account; keep only accounts
    account_pks = {
        row[0]
        for row in connection.execute(
            "SELECT Z_PK FROM ZICCLOUDSYNCINGOBJECT WHERE Z_ENT = "
            "(SELECT Z_ENT FROM Z_PRIMARYKEY WHERE Z_NAME = 'ICAccount')"
        )
    }
    accounts = {a.id: a for a in db.get_accounts() if a.id in account_pks}
    folders = {f.id: f for f in db.get_folders(accounts)}
    account_ids = {pk: f"x-coredata://{z_uuid}/ICAccount/p{pk}" for pk in accounts}
    tags = _load_tags(connection)

    records = []
    for note in db.get_notes(accounts, folders):
        locked = note.is_password_protected
        records.append(
            NoteRecord(
                id=note.applescript_id
                or f"x-coredata://{z_uuid}/ICNote/p{note.note_id}",
                name=note.title or "",
                account=note.account.name,
                account_id=account_ids[note.account.id],
                folder=note.folder.name,
                folder_path=note.folder.get_path(),
                # the text of a locked note is encrypted; Notes.app returns ""
                plaintext="" if locked else note.content or "",
                creation_date=_whole_seconds(note.creation_date),
                modification_date=_whole_seconds(note.modification_date),
                password_protected=locked,
                pinned=note.is_pinned,
                tags=() if locked else tags.get(note.note_id, ()),
            )
        )
    return {account_ids[pk]: a.name for pk, a in accounts.items()}, records


def _load_tags(connection: sqlite3.Connection) -> dict[int, tuple[str, ...]]:
    """Return tags of each note by primary key.

    Tags are inline hashtag objects. apple-notes-parser falls back to finding #words
    in the text, which gives false tags, so tags are read here instead.
    """
    try:
        rows = connection.execute(
            "SELECT COALESCE(ZNOTE1, ZNOTE), ZALTTEXT FROM ZICCLOUDSYNCINGOBJECT "
            "WHERE ZTYPEUTI1 = 'com.apple.notes.inlinetextattachment.hashtag'"
        ).fetchall()
    except sqlite3.OperationalError:
        # databases from before macOS 11 have no tags (or these columns)
        return {}
    tags: dict[int, set[str]] = {}
    for note_pk, alt_text in rows:
        if note_pk is not None and (tag := (alt_text or "").lstrip("#")):
            tags.setdefault(note_pk, set()).add(tag)
    return {pk: tuple(sorted(t, key=str.casefold)) for pk, t in tags.items()}


def note_data_features(zdata: bytes | None) -> list[str]:
    """Return the kinds of content besides plain text in a note's ZDATA protobuf"""
    if not zdata or zdata[:2] != b"\x1f\x8b":
        # empty, or locked (encrypted) notes, which can't be inspected
        return []
    from apple_notes_parser.notestore_pb2 import NoteStoreProto

    proto = NoteStoreProto()
    proto.ParseFromString(gzip.decompress(zdata))
    note = proto.document.note
    # notes created from HTML (as macnotesapp does) have a bold, large-font first line
    # instead of the Title style; that survives Markdown as a heading, so ignore it.
    # Run lengths count UTF-16 code units.
    title = note.note_text.split("\n", 1)[0]
    title_end = len(title.encode("utf-16-le")) // 2
    features = set()
    start = 0
    for run in note.attribute_run:
        in_title = start < title_end
        start += run.length
        if run.HasField("paragraph_style"):
            style = run.paragraph_style
            style_type = style.style_type if style.HasField("style_type") else None
            # the title line, including its newline, has the Title style; so can
            # lines in the body
            if style_type in (STYLE_HEADING, STYLE_SUBHEADING) or (
                style_type == STYLE_TITLE and start > title_end + 1
            ):
                features.add("headings")
            elif style_type == STYLE_MONOSPACED:
                features.add("monospaced")
            elif style_type in STYLE_LISTS:
                features.add("lists")
            elif style_type == STYLE_CHECKLIST or style.HasField("checklist"):
                features.add("checklists")
            if style.alignment:
                features.add("alignment")
            if style.indent_amount and style_type not in (
                *STYLE_LISTS,
                STYLE_CHECKLIST,
            ):
                features.add("indentation")
            if style.block_quote:
                features.add("block quotes")
        if run.font_weight and not in_title:
            features.add("bold or italic")
        if run.underlined or run.strikethrough:
            features.add("underline or strikethrough")
        if run.superscript:
            features.add("superscript or subscript")
        if (
            run.HasField("font")
            and (run.font.font_name or run.font.point_size)
            and not in_title
        ):
            features.add("fonts")
        if run.HasField("color"):
            features.add("colors")
        if run.emphasis_style:
            features.add("highlights")
        if run.link:
            features.add("links")
        if run.HasField("attachment_info"):
            type_uti = run.attachment_info.type_uti
            if type_uti in ATTACHMENT_FEATURES:
                features.add(ATTACHMENT_FEATURES[type_uti])
            elif type_uti.startswith("com.apple.notes.inlinetextattachment."):
                features.add("inline objects")
            else:
                features.add("attachments")
    return sorted(features)


def _whole_seconds(date: datetime | None) -> datetime | None:
    """Drop fractions of a second, which ScriptingBridge doesn't return"""
    return date.replace(microsecond=0) if date else date


def _primary_key(note_id: str) -> int:
    """Return the database primary key from an id like x-coredata://<UUID>/ICNote/p123"""
    if match := re.fullmatch(r"x-coredata://[^/]+/ICNote/p(\d+)", note_id):
        return int(match[1])
    raise ValueError(f"Not a note ID: {note_id}")


def _fold(text: str) -> str:
    """Fold case and remove diacritics, like NSPredicate's [cd]"""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _contains_any(text: str, values: list[str]) -> bool:
    folded = _fold(text)
    return any(_fold(value) in folded for value in values)
