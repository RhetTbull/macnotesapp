"""Python interface to macOS Notes.app"""

from __future__ import annotations

import os
import re
from datetime import datetime
from functools import cached_property
from typing import Any, Optional

import AppKit
import ScriptingBridge

from ._version import __version__
from .script_loader import run_script
from .utils import NSDate_to_datetime, OSType


class AppleScriptError(Exception):
    def __init__(self, *message):
        super().__init__(*message)


class NotesApp:
    """Represents Notes.app instance"""

    def __init__(self):
        """create new NotesApp object"""
        self._app = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_(
            "com.apple.Notes"
        )

    @property
    def app(self):
        """Return Notes.app SBApplication object"""
        return self._app

    @property
    def accounts(self) -> list[str]:
        """Return list of accounts"""
        return [a.name() for a in self._app.accounts()]

    @property
    def default_account(self) -> str:
        """Return name of default account"""
        return str(self._app.defaultAccount().name())

    def notes(
        self,
        name: list[str] | None = None,
        body: list[str] | None = None,
        text: list[str] | None = None,
        password_protected: bool | None = None,
        accounts: list[str] | None = None,
        id: list[str] | None = None,
    ) -> list["Note"]:
        """Return Note object for all notes contained in Notes.app or notes filtered by property"""
        # TODO: should this be a generator?
        account_list = self.app.accounts()
        if accounts:
            format_str = "name == %@" + " OR name == %@ " * (len(accounts) - 1)
            predicate = AppKit.NSPredicate.predicateWithFormat_(format_str, accounts)
            account_list = account_list.filteredArrayUsingPredicate_(predicate)
        note_objects = []
        for account in account_list:
            notes = account.notes()
            format_str = ""
            if name and notes:
                format_str += (
                    " (name contains[cd] %@)"
                    + " OR (name contains[cd] %@)" * (len(name) - 1)
                )
            if body and notes:
                format_str += (
                    " (plaintext contains[cd] %@)"
                    + " OR (plaintext contains[cd] %@)" * (len(body) - 1)
                )
            if text and notes:
                format_str += (
                    " (name contains[cd] %@)"
                    + " OR (name contains[cd] %@)" * (len(text) - 1)
                    + " OR (plaintext contains[cd] %@) "
                    + " OR (plaintext contains[cd] %@)" * (len(text) - 1)
                )
            if password_protected is not None and notes:
                format_str += (
                    " (passwordProtected == TRUE)"
                    if password_protected
                    else (" (passwordProtected == FALSE)")
                )
            if id and notes:
                format_str += " (id == %@)" + " OR (id == %@)" * (len(id) - 1)
            if format_str:
                # have one or more search predicates; filter notes
                args = name or []
                args += body or []
                if text:
                    args += text * 2
                args += id or []
                predicate = AppKit.NSPredicate.predicateWithFormat_(format_str, *args)
                notes = notes.filteredArrayUsingPredicate_(predicate)
            note_objects.extend(Note(note) for note in notes)
        return note_objects

    @property
    def selection(self) -> list["Note"]:
        """Return selected notes"""
        notes = self.app.selection()
        return [Note(note) for note in notes]

    @property
    def version(self) -> str:
        """Return version of Notes.app"""
        return str(self.app.version())

    def make_note(self, name: str, body: str) -> "Note":
        """Create new note in default folder of default account"""
        properties = {
            "body": f"<b>{name}</b><br />{body}",
        }
        note = (
            self.app.classForScriptingClass_("note")
            .alloc()
            .initWithData_andProperties_(None, properties)
        )
        print(note, type(note))
        return
        if noteid := run_script("notesMakeNote", name, body):
            default_account = run_script("notesGetDefaultAccount")
            return Note(default_account, noteid)
        raise AppleScriptError(f"Could not create note '{name}' with body '{body}'")

    def account(self, account: Optional[str] = None) -> "Account":
        """Return Account object for account; if None, returns default account"""
        account = account or self.default_account
        predicate = AppKit.NSPredicate.predicateWithFormat_("name == %@", account)
        accounts = self.app.accounts().filteredArrayUsingPredicate_(predicate)
        if not accounts:
            raise ValueError(f"Could not find account {account}")
        account_obj = accounts[0]
        return Account(account_obj)

    def activate(self):
        """Activate Notes.app"""
        run_script("notesActivate")

    def quit(self):
        """Quit Notes.app"""
        run_script("notesQuit")

    def __len__(self):
        """Return count of notes"""

    def __iter__(self):
        """Generator to yield all notes contained in Notes.app"""
        for account in self.app.accounts():
            notes = account.notes()
            for note in notes:
                yield Note(note)


class Account:
    """Notes.app Account object"""

    def __init__(self, account: ScriptingBridge.SBObject):
        self._account = account

    @property
    def name(self):
        """Return name of account"""
        return self._account.name()
        # return str(self._run_script("accountName"))

    @property
    def folders(self) -> list[str]:
        """Return list of folder names"""
        if folders := self._account.folders():
            return [str(f.name()) for f in folders]
        return [str(f) for f in self._run_script("accountGetFolderNames")]

    @property
    def default_folder(self) -> str:
        """Return default folder for account"""
        if default_folder := self._account.defaultFolder():
            return default_folder.name()
        return str(self._run_script("accountGetDefaultFolder"))

    @property
    def id(self) -> str:
        """Return ID of account"""
        if id_ := self._account.id():
            return id_
        return str(self._run_script("accountID"))

    @property
    def notes(self) -> list["Note"]:
        """Return all notes in account"""
        # ZZZ
        all_notes = self._run_script("accountGetAllNotes")
        return [Note(self._account, id_) for id_ in all_notes]

    def show(self):
        """Show account in Notes.app UI"""
        self._run_script("accountShow")

    def make_note(self, name: str, body: str, folder: Optional[str] = None) -> "Note":
        """Create new note

        Args:
            name: name of note
            body: body of note (plaintext or HTML)
            folder: create note in folder; if None, uses default folder for account
        """
        folder = folder or self.default_folder
        account = self._account
        if noteid := run_script(
            "notesMakeNoteWithAccount", account, folder, name, body
        ):
            return Note(account, noteid)
        raise AppleScriptError(
            f"Could not create note '{name}' with body '{body}' in folder '{folder}' of account '{account}'"
        )

    def _run_script(self, script, *args):
        return run_script(script, self.name, *args)

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

    def __init__(self, note: ScriptingBridge.SBObject):
        self._note = note

    @property
    def account(self) -> str:
        """Account note belongs to"""
        # can't determine this easily from the note object
        # so need to use AppleScript
        return str(run_script("noteGetAccount", self.id))

    @cached_property
    def id(self) -> str:
        """Note ID"""
        if note_id := self._note.id():
            return str(note_id)
        else:
            # if note object created from selection or predicate it may show ID of 0
            # but the ID is in the string representation of the object so parse it
            return self._parse_id_from_object() or 0

    @property
    def name(self) -> str:
        """Name of note"""
        return (
            str(name)
            if (name := self._note.name())
            else self._run_script("noteGetName")
        )

    @name.setter
    def name(self, name: str):
        """Set name of note"""
        self._note.setValue_forKey_(name, "name")
        if self.name != name:
            self._run_script("noteSetName", name)

    @property
    def body(self) -> str:
        """Return body of note"""
        return (
            str(body)
            if (body := self._note.body())
            else str(self._run_script("noteGetBody"))
        )

    @body.setter
    def body(self, body: str):
        """Set body of note"""
        self._note.setValue_forKey_(body, "body")
        if self.body != body:
            self._run_script("noteSetBody", body)

    @property
    def plaintext(self) -> str:
        """Return plaintext of note"""
        return (
            str(plaintext)
            if (plaintext := self._note.plaintext())
            else str(self._run_script("noteGetPlainText"))
        )

    @property
    def creation_date(self) -> datetime:
        """Return creation date of note"""
        if date := self._note.creationDate():
            return NSDate_to_datetime(date)
        else:
            return self._run_script("noteGetCreationDate")

    @property
    def modification_date(self) -> datetime:
        """Return modification date of note"""
        if date := self._note.modificationDate():
            return NSDate_to_datetime(date)
        else:
            return self._run_script("noteGetModificationDate")

    @property
    def password_protected(self) -> bool:
        """Return password protected status of note"""
        # return self._note.passwordProtected() # returns False even when note is password protected, at least on Catalina
        return bool(self._run_script("noteGetPasswordProtected"))

    @property
    def folder(self) -> str:
        """Return folder note is contained in"""
        # calling container() method on note object returns None
        # in many cases, so use AppleScript instead
        return self._note.container().name() or self._run_script("noteGetContainer")

    @property
    def attachments(self) -> list["Attachment"]:
        """Return list of attachments for note"""
        return [Attachment(attachment) for attachment in self._note.attachments()]

    def show(self):
        """Show note in Notes.app UI"""
        self._run_script("noteShow")

    def asdict(self, body: str = "html") -> dict[str, Any]:
        """Return dict representation of note

        Args:
            body: "html" or "plaintext" to return body of note in that format
        """
        return {
            "account": self.account,
            "id": self.id,
            "name": self.name,
            "body": self.body if body == "html" else self.plaintext,
            "creation_date": self.creation_date,
            "modification_date": self.modification_date,
            "password_protected": self.password_protected,
            "folder": self.folder,
        }

    def _run_script(self, script, *args):
        """Run AppleScript script"""
        print(f"running script: {script} {args}")
        return run_script(script, self.account, self.id, *args)

    def _parse_id_from_object(self) -> str:
        """Parse the ID from the object representation when it can't be determined by ScriptingBridge"""

        # there are some conditions (e.g. using selection on Catalina or using a predicate)
        # where the ScriptingBridge sets the object ID to 0
        # I haven't been able to figure out why but in this case, the id can be determined
        # by examining the string representation of the object which looks like this:
        # <SBObject @0x7fd721544690: <class ''> id "x-coredata://19B82A76-B3FE-4427-9C5E-5107C1E3CA57/IMAPNote/p87" of application "Notes" (55036)>
        match = re.search(r'id "(x-coredata://.+?)"', str(self._note))
        if match:
            return match.group(1)
        return None

    def __repr__(self):
        return f"Note({self.id})"

    def __eq__(self, other):
        return (self.id, self.account) == (other.id, other.account)

    def __hash__(self):
        return hash(repr(self))


class Attachment:
    """Notes.app Attachment object"""

    def __init__(self, attachment: ScriptingBridge.SBObject):
        self._attachment = attachment

    @property
    def id(self) -> str:
        """ID of attachment"""
        return str(self._attachment.id())

    @property
    def name(self) -> str:
        """Name of attachment"""
        return str(name) if (name := self._attachment.name()) else None

    @property
    def creation_date(self) -> datetime:
        """Creation date of attachment"""
        return NSDate_to_datetime(self._attachment.creationDate())

    @property
    def modification_date(self) -> datetime:
        """Modification date of attachment"""
        return NSDate_to_datetime(self._attachment.modificationDate())

    @property
    def content_identifier(self) -> str:
        """The content-id URL in the note's HTML"""
        return str(ci) if (ci := self._attachment.contentIdentifier()) else None

    @property
    def URL(self) -> str:
        """For URL attachments, the URL the attachment represents"""
        return str(url) if (url := self._attachment.URL()) else None

    def save(self, path: str | bytes | os.PathLike) -> str:
        """Save attachment to file"""
        if not os.path.exists(str(path)):
            raise FileNotFoundError(f"Path does not exist: {path}")

        url = AppKit.NSURL.alloc().initFileURLWithPath_(
            os.path.join(str(path), self.name)
        )
        self._attachment.saveIn_as_(url, OSType("item"))
        return str(url.path())
