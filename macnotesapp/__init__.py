"""Python to AppleScript bridge for automating Notes.app on macOS"""

from datetime import datetime
from typing import List, Optional

from .script_loader import run_script


class AppleScriptError(Exception):
    def __init__(self, *message):
        super().__init__(*message)


class NotesApp:
    """Represents Notes.app instance"""

    def __init__(self):
        """create new NotesApp object"""

    @property
    def accounts(self) -> List[str]:
        """Return list of accounts"""
        return run_script("notesGetAccounts")

    @property
    def default_account(self) -> str:
        """Return name of default account"""
        return run_script("notesGetDefaultAccount")

    @property
    def notes(self) -> List["Note"]:
        """Return Note object for all notes contained in Notes.app"""
        all_notes = run_script("notesGetAllNotes")
        # result is [[account, [note ids], ...]]
        notes = []
        for account, note_ids in all_notes:
            notes.extend(Note(account, id_) for id_ in note_ids)
        return notes

    @property
    def selection(self) -> List["Note"]:
        """Return selected notes"""
        notes = run_script("notesGetSelected")
        return [Note(account, id_) for account, id_ in notes]

    @property
    def version(self):
        """Return version of Notes.app"""
        return run_script("notesVersion")

    def make_note(self, name: str, body: str) -> "Note":
        """Create new note in default folder of default account"""
        if noteid := run_script("notesMakeNote", name, body):
            default_account = run_script("notesGetDefaultAccount")
            return Note(default_account, noteid)
        raise AppleScriptError(f"Could not create note '{name}' with body '{body}'")

    def find_notes(
        self, name: Optional[str] = None, text: Optional[str] = None
    ) -> List["Note"]:
        """Find notes either by name or text contained in the note

        Args:
            name: str to search for in note name
            text: str to search for in note body

        Note: If both name and text provided, result is the union of the two, that is, notes where either name or body match

        Returns:
            list of Note objects for matching notes
        """
        name_matches = dict(run_script("notesFindWithName", name)) if name else {}
        text_matches = dict(run_script("notesFindWithText", text)) if text else {}

        # union of results
        all_matches = name_matches.copy()
        for account, ids in text_matches.items():
            if account in all_matches:
                all_matches[account] += ids
            else:
                all_matches[account] = ids

        # return Note objects
        matches = []
        for account in all_matches:
            matches.extend([Note(account, id_) for id_ in set(all_matches[account])])
        return matches

    def activate(self):
        """Activate Notes.app"""
        run_script("notesActivate")

    def quit(self):
        """Quit Notes.app"""
        run_script("notesQuit")

    def __len__(self):
        """Return count of notes"""
        return run_script("notesGetCount")

    def __iter__(self):
        """Generator to yield all notes contained in Notes.app"""
        all_notes = run_script("notesGetAllNotes")
        # result is [[account, [note ids], ...]]
        for account, note_ids in all_notes:
            for id_ in note_ids:
                yield Note(account, id_)


class Account:
    """Notes.app Account object"""

    def __init__(self, account: str):
        self._account = account

    @property
    def name(self):
        return self._run_script("accountName")

    @property
    def default_folder(self) -> str:
        """Return default folder for account"""
        return self._run_script("accountGetDefaultFolder")

    @property
    def id(self) -> str:
        """Return ID of account"""
        return self._run_script("accountID")

    @property
    def notes(self) -> List["Note"]:
        """Return all notes in account"""
        all_notes = self._run_script("accountGetAllNotes")
        return [Note(self._account, id_) for id_ in all_notes]

    def show(self):
        """Show account in Notes.app UI"""
        self._run_script("accountShow")

    def find_notes(
        self, name: Optional[str] = None, text: Optional[str] = None
    ) -> List["Note"]:
        """Find notes either by name or text contained in the note for account

        Args:
            name: str to search for in note name
            text: str to search for in note body

        Note: If both name and text provided, result is the union of the two, that is, notes where either name or body match

        Returns:
            list of Note objects for matching notes
        """
        name_matches = self._run_script("accountFindWithName", name) if name else []
        text_matches = self._run_script("accountFindWithText", text) if text else []

        # union of results
        all_matches = name_matches + text_matches

        # return Note objects
        return [Note(self._account, id_) for id_ in set(all_matches)]

    def _run_script(self, script, *args):
        return run_script(script, self._account, *args)

    def __len__(self):
        """Return count of notes"""
        return self._run_script("accountGetCount")

    def __iter__(self):
        """Generator to yield all notes contained in Notes.app"""
        all_notes = self._run_script("accountGetAllNotes")
        for id_ in all_notes:
            yield Note(self._account, id_)


class Note:
    """Notes.app Note object"""

    def __init__(self, account: str, id_: str):
        self._account = account
        self._id = id_

    @property
    def name(self) -> str:
        """Name of note"""
        return self._run_script("noteGetName")

    @property
    def body(self) -> str:
        """Return body of note"""
        return self._run_script("noteGetBody")

    @property
    def plaintext(self) -> str:
        """Return plaintext of note"""
        return self._run_script("noteGetPlainText")

    @property
    def creation_date(self) -> datetime:
        """Return creation date of note"""
        return self._run_script("noteGetCreationDate")

    @property
    def modification_date(self) -> datetime:
        """Return modification date of note"""
        return self._run_script("noteGetModificationDate")

    @property
    def password_protected(self) -> bool:
        """Return password protected status of note"""
        return self._run_script("noteGetPasswordProtected")

    @property
    def folder(self) -> str:
        """Return folder note is contained in"""
        return self._run_script("noteGetContainer")

    def show(self):
        """Show note in Notes.app UI"""
        self._run_script("noteShow")

    def _run_script(self, script, *args):
        return run_script(script, self._account, self._id, *args)
