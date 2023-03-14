"""Python interface to macOS Notes.app"""

from __future__ import annotations

import os
import pathlib
import re
from datetime import datetime
from functools import cached_property
from typing import Any, Generator, Optional

import AppKit
import ScriptingBridge

from ._version import __version__
from .script_loader import run_script
from .utils import NSDate_to_datetime, OSType


class AppleScriptError(Exception):
    """Error raised when AppleScript fails to execute"""

    def __init__(self, *message):
        super().__init__(*message)


class ScriptingBridgeError(Exception):
    """ "Errors raised when ScriptingBridge fails to execute"""

    def __init__(self, *message):
        super().__init__(*message)


def parse_id_from_object(obj: ScriptingBridge.SBObject) -> str:
    """Parse the ID from the object representation when it can't be determined by ScriptingBridge"""

    # there are some conditions (e.g. using selection on Catalina or using a predicate)
    # where the ScriptingBridge sets the object ID to 0
    # I haven't been able to figure out why but in this case, the id can be determined
    # by examining the string representation of the object which looks like this:
    # <SBObject @0x7fd721544690: <class ''> id "x-coredata://19B82A76-B3FE-4427-9C5E-5107C1E3CA57/IMAPNote/p87" of application "Notes" (55036)>
    if match := re.search(r'id "(x-coredata://.+?)"', str(obj)):
        return match[1]
    return None


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
        id: list[str] | None = None,
        accounts: list[str] | None = None,
    ) -> list["Note"]:
        """Return Note object for all notes contained in Notes.app or notes filtered by property.

        Args:
            name: list of note names to filter by
            body: list of note bodies to filter by
            text: list of note text to filter by
            password_protected: filter by password protected notes
            id: list of note ids to filter by
            accounts: list of account names to filter by

        Returns:
            list of Note objects
        """
        # TODO: should this be a generator?
        account_list = self.app.accounts()
        if accounts:
            format_str = "name == %@" + " OR name == %@ " * (len(accounts) - 1)
            predicate = AppKit.NSPredicate.predicateWithFormat_(format_str, accounts)
            account_list = account_list.filteredArrayUsingPredicate_(predicate)
        notes = []
        for account in account_list:
            notes.extend(
                Account(account).notes(name, body, text, password_protected, id)
            )
        return notes

    def noteslist(
        self,
        name: list[str] | None = None,
        body: list[str] | None = None,
        text: list[str] | None = None,
        password_protected: bool | None = None,
        id: list[str] | None = None,
        accounts: list[str] | None = None,
    ) -> "NotesList":
        """Return NoteList object for all notes contained in account or notes filtered by property.

        Args:
            name: list of note names to filter by
            body: list of note bodies to filter by
            text: list of note text to filter by
            password_protected: filter by password protected notes
            id: list of note ids to filter by
            accounts: list of account names to filter by

        Returns:
            NotesList object
        """
        account_list = self.app.accounts()
        if accounts:
            format_str = "name == %@" + " OR name == %@ " * (len(accounts) - 1)
            predicate = AppKit.NSPredicate.predicateWithFormat_(format_str, accounts)
            account_list = account_list.filteredArrayUsingPredicate_(predicate)
        noteslists = [
            Account(account)._noteslist(
                name=name,
                body=body,
                text=text,
                password_protected=password_protected,
                id=id,
            )
            for account in account_list
        ]
        return NotesList(*noteslists)

    @property
    def selection(self) -> list["Note"]:
        """Return lit of Note objects for selected notes"""
        notes = self.app.selection()
        return [Note(note) for note in notes]

    @property
    def version(self) -> str:
        """Return version of Notes.app"""
        return str(self.app.version())

    def make_note(
        self, name: str, body: str, attachments: list[str] | None = None
    ) -> "Note":
        """Create new note in default folder of default account.

        Args:
            name: name of notes
            body: body of note as HTML text
            attachments: optional list of paths to attachments to add to note

        Returns:
            newly created Note object
        """
        # reference: https://developer.apple.com/documentation/scriptingbridge/sbobject/1423973-initwithproperties
        account = Account(self.app.defaultAccount())
        note = account.make_note(name, body)
        if attachments:
            for attachment in attachments:
                note.add_attachment(attachment)
        return note

    def account(self, account: Optional[str] = None) -> "Account":
        """Return Account object for account or default account if account is None.

        Arg:
            account: name of account to return. If None, return default account.

        Returns:
            Account object
        """
        account = account or self.default_account
        predicate = AppKit.NSPredicate.predicateWithFormat_("name == %@", account)
        accounts = self.app.accounts().filteredArrayUsingPredicate_(predicate)
        if not accounts:
            raise ValueError(f"Could not find account {account}")
        account_obj = accounts[0]
        return Account(account_obj)

    def activate(self) -> None:
        """Activate Notes.app"""
        run_script("notesActivate")

    def quit(self) -> None:
        """Quit Notes.app"""
        run_script("notesQuit")

    def __len__(self) -> int:
        """Return count of notes in Notes.app"""
        return sum(len(account.notes()) for account in self.app.accounts())

    def __iter__(self) -> Generator["Note", None, None]:
        """Generator to yield Note object for all notes contained in Notes.app"""
        for account in self.app.accounts():
            notes = account.notes()
            for note in notes:
                yield Note(note)


class Account:
    """Notes.app Account object"""

    def __init__(self, account: ScriptingBridge.SBObject):
        """Initialize Account object"""
        self._account = account

    @property
    def name(self) -> str:
        """Return name of account"""
        return self._account.name()
        # return str(self._run_script("accountName"))

    @property
    def folders(self) -> list[str]:
        """Return list of folder names in account"""
        if folders := self._account.folders():
            return [str(f.name()) for f in folders]
        return [str(f) for f in self._run_script("accountGetFolderNames")]

    @property
    def default_folder(self) -> str:
        """Return name of default folder for account"""
        if default_folder := self._account.defaultFolder():
            return default_folder.name()
        return str(self._run_script("accountGetDefaultFolder"))

    @cached_property
    def id(self) -> str:
        """Return ID of account"""
        if id_ := self._account.id():
            return id_
        return str(self._run_script("accountID"))

    def notes(
        self,
        name: list[str] | None = None,
        body: list[str] | None = None,
        text: list[str] | None = None,
        password_protected: bool | None = None,
        id: list[str] | None = None,
    ) -> list["Note"]:
        """Return Note object for all notes contained in account or notes filtered by property.

        Args:
            name: list of note names to filter by
            body: list of note bodies to filter by
            text: list of note text to filter by
            password_protected: filter by password protected notes
            id: list of note ids to filter by

        Returns:
            list of Note objects
        """
        # TODO: should this be a generator?
        notes = self._account.notes()
        format_strings = []
        if name and notes:
            name_strings = ["(name contains[cd] %@)"] * len(name)
            format_strings.append(name_strings)
        if body and notes:
            body_strings = ["(plaintext contains[cd] %@)"] * len(body)
            format_strings.append(body_strings)
        if text and notes:
            text_strings = ["(name contains[cd] %@)"] * len(text)
            text_strings.extend(["(plaintext contains[cd] %@)"] * len(text))
            format_strings.append(text_strings)
        if password_protected is not None and notes:
            password_string = (
                ["(passwordProtected == TRUE)"]
                if password_protected
                else ["(passwordProtected == FALSE)"]
            )
            format_strings.append(password_string)
        if id and notes:
            id_string = ["(id == %@)"] * len(id)
            format_strings.append(id_string)
        if format_strings:
            # have one or more search predicates; filter notes
            args = name or []
            args += body or []
            if text:
                args += text * 2
            args += id or []
            or_strings = [" OR ".join(strings) for strings in format_strings]
            format_str = "(" + ") AND (".join(or_strings) + ")"
            predicate = AppKit.NSPredicate.predicateWithFormat_(format_str, *args)
            notes = notes.filteredArrayUsingPredicate_(predicate)
        return [Note(note) for note in notes.get()]

    def noteslist(
        self,
        name: list[str] | None = None,
        body: list[str] | None = None,
        text: list[str] | None = None,
        password_protected: bool | None = None,
        id: list[str] | None = None,
    ) -> "NotesList":
        """Return NoteList object for all notes contained in account or notes filtered by property.

        Args:
            name: list of note names to filter by
            body: list of note bodies to filter by
            text: list of note text to filter by
            password_protected: filter by password protected notes
            id: list of note ids to filter by

        Returns:
            NotesList object"""
        notes = self._noteslist(name, body, text, password_protected, id)
        return NotesList(notes)

    def folder(self, folder: str) -> "Folder":
        """Return Folder object for folder with name folder."""
        folder_obj = self._folder_for_name(folder)
        return Folder(folder_obj)

    def show(self):
        """Show account in Notes.app UI"""
        self._run_script("accountShow")

    def make_note(
        self,
        name: str,
        body: str,
        folder: str | None = None,
        attachments: list[str] | None = None,
    ) -> "Note":
        """Create new note in account

        Args:
            name: name of note
            body: body of note
            folder: optional folder to create note in; if None, uses default folder
            attachments: optional list of file paths to attach to note

        Returns:
            Note object for new note

        Raises:
            ScriptingBridgeError: if note could not be created
            FileNotFoundError: if attachment file could not be found
        """

        # reference: https://developer.apple.com/documentation/scriptingbridge/sbobject/1423973-initwithproperties
        notes_app = NotesApp()
        folder_obj = (
            self._folder_for_name(folder) if folder else self._account.defaultFolder()
        )
        properties = {
            "body": f"<div><h1>{name}</h1></div>\n{body}",
        }
        note = (
            notes_app.app.classForScriptingClass_("note")
            .alloc()
            .initWithProperties_(properties)
        )
        notes = folder_obj.notes()
        len_before = len(notes)
        notes.addObject_(note)
        len_after = len(notes)

        if len_after <= len_before:
            raise ScriptingBridgeError(
                f"Could not create note '{name}' with body '{body}'"
            )

        new_note = Note(note)
        if attachments:
            for attachment in attachments:
                if not os.path.exists(attachment):
                    raise FileNotFoundError(f"File {attachment} does not exist")
                new_note.add_attachment(attachment)
        return new_note

    def _noteslist(
        self,
        name: list[str] | None = None,
        body: list[str] | None = None,
        text: list[str] | None = None,
        password_protected: bool | None = None,
        id: list[str] | None = None,
    ) -> ScriptingBridge.SBElementArray:
        """Return SBElementArray for all notes contained in account or notes filtered by property"""
        notes = self._account.notes()
        format_strings = []
        if name and notes:
            name_strings = ["(name contains[cd] %@)"] * len(name)
            format_strings.append(name_strings)
        if body and notes:
            body_strings = ["(plaintext contains[cd] %@)"] * len(body)
            format_strings.append(body_strings)
        if text and notes:
            text_strings = ["(name contains[cd] %@)"] * len(text)
            text_strings.extend(["(plaintext contains[cd] %@)"] * len(text))
            format_strings.append(text_strings)
        if password_protected is not None and notes:
            password_string = (
                ["(passwordProtected == TRUE)"]
                if password_protected
                else ["(passwordProtected == FALSE)"]
            )
            format_strings.append(password_string)
        if id and notes:
            id_string = ["(id == %@)"] * len(id)
            format_strings.append(id_string)
        if format_strings:
            # have one or more search predicates; filter notes
            args = name or []
            args += body or []
            if text:
                args += text * 2
            args += id or []
            or_strings = [" OR ".join(strings) for strings in format_strings]
            format_str = "(" + ") AND (".join(or_strings) + ")"
            predicate = AppKit.NSPredicate.predicateWithFormat_(format_str, *args)
            notes = notes.filteredArrayUsingPredicate_(predicate)
        return notes

    def _folder_for_name(self, folder: str) -> ScriptingBridge.SBObject:
        """Return ScriptingBridge folder object for folder"""
        if folder_objs := self._account.folders().filteredArrayUsingPredicate_(
            AppKit.NSPredicate.predicateWithFormat_("name == %@", folder)
        ):
            return folder_objs[0]
        else:
            raise ValueError(f"Could not find folder {folder}")

    def _run_script(self, script, *args):
        return run_script(script, self.name, *args)

    def __len__(self) -> int:
        """Return count of notes"""
        return len(self._account.notes())
        # return self._run_script("accountGetCount")

    def __iter__(self) -> Generator[Note, None, None]:
        """Generator to yield all notes contained in Notes.app"""
        for note in self._account.notes():
            yield Note(note)


class NotesList:
    """NotesList object for list of notes.
    Represents an SBElementArray of notes as returned by noteslist()
    """

    def __init__(self, *noteslist: ScriptingBridge.SBElementArray):
        self._noteslist = noteslist

    @property
    def id(self) -> list[str]:
        """Return ID of every note in list as list of strings"""
        return self._apply_selector("id")

    @property
    def name(self) -> list[str]:
        """Return name of every note in list as list of strings"""
        return self._apply_selector("name")

    @property
    def body(self) -> list[str]:
        """Return body of every note in list as list of strings"""
        return self._apply_selector("body")

    @property
    def plaintext(self) -> list[str]:
        """Return plaintext of every note in list as list of strings"""
        return self._apply_selector("plaintext")

    @property
    def container(self) -> list[str]:
        """Return container of every note in list as list of strings"""
        return self._apply_selector("container")

    @property
    def folder(self) -> list[str]:
        """Return folder of every note in list as list of strings"""
        return self.container

    @property
    def creation_date(self) -> list[datetime]:
        """Return creation date of every note in list as list of datetimes"""
        return self._apply_selector("creationDate")

    @property
    def modification_date(self) -> list[datetime]:
        """Return modification date of every note in list as list of datetimes"""
        return self._apply_selector("modificationDate")

    @property
    def password_protected(self) -> list[bool]:
        """Return whether every note in list is password protected as list of bools"""
        return self._apply_selector("passwordProtected")

    def asdict(self) -> list[dict[str, str]]:
        """Return list of dict representations of note"""
        return [
            {
                "id": note[0],
                "name": note[1],
                "body": note[2],
                "plaintext": note[3],
                "creation_date": note[4],
                "modification_date": note[5],
                "password_protected": note[6],
                "folder": note[7],
            }
            for note in zip(
                self.id,
                self.name,
                self.body,
                self.plaintext,
                self.creation_date,
                self.modification_date,
                self.password_protected,
                self.container,
            )
        ]

    def _apply_selector(self, selector) -> list[str]:
        """Return note properties in list that pass selector"""
        results_list = []
        for noteslist in self._noteslist:
            results = noteslist.arrayByApplyingSelector_(selector)
            if selector in ["creationDate", "modificationDate"]:
                results_list.extend(NSDate_to_datetime(date) for date in results)
            elif selector == "container":
                results_list.extend(container.name() for container in results)
            else:
                results_list.extend(list(results))
        return results_list

    def __len__(self) -> int:
        """Return count of notes in list"""
        return len(self.id)


class Note:
    """Note object representing a note in Notes.app"""

    def __init__(self, note: ScriptingBridge.SBObject):
        self._note = note

    @property
    def account(self) -> str:
        """Return name of account note belongs to."""
        # can't determine this easily from the note object
        # so may to use AppleScript
        return str(run_script("noteGetAccount", self.id))

    @cached_property
    def id(self) -> str:
        """Return note ID"""
        if note_id := self._note.id():
            return str(note_id)
        else:
            # if note object created from selection or predicate it may show ID of 0
            # but the ID is in the string representation of the object so parse it
            return parse_id_from_object(self._note) or 0

    @property
    def name(self) -> str:
        """Return name of note"""
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
        """Return creation date of note as datetime"""
        if date := self._note.creationDate():
            return NSDate_to_datetime(date)
        else:
            return self._run_script("noteGetCreationDate")

    @property
    def modification_date(self) -> datetime:
        """Return modification date of note as datetime"""
        if date := self._note.modificationDate():
            return NSDate_to_datetime(date)
        else:
            return self._run_script("noteGetModificationDate")

    @property
    def password_protected(self) -> bool:
        """Return password protected status of note"""
        # return self._note.passwordProtected() # returns False even when note is password protected, at least on Catalina
        # TODO: appears to work correctly on Ventura so need to check OS version
        return bool(self._run_script("noteGetPasswordProtected"))

    @property
    def folder(self) -> str:
        """Return name of folder note is contained in"""
        # calling container() method on note object returns None
        # in many cases, so use AppleScript instead
        return self._note.container().name() or self._run_script("noteGetContainer")

    @property
    def attachments(self) -> list["Attachment"]:
        """Return list of attachments for note as Attachment objects"""

        # .attachments() method on note object sometimes returns duplicates, e.g each attachment is returned twice
        # filter out duplicates by comparing attachment ID
        # this appears to happen only with attachments added via AppleScript or ScriptingBridge
        # not with those natively added in Notes.app
        attachments = [
            Attachment(attachment) for attachment in self._note.attachments()
        ]
        return [
            attachment
            for i, attachment in enumerate(attachments)
            if attachment.id not in [a.id for a in attachments[:i]]
        ]

    def add_attachment(self, path: str) -> "Attachment":
        """Add attachment to note

        Args:
            path: path to file to attach

        Returns:
            Attachment object for attached file

        Raises:
            FileNotFoundError: if file not found
        """

        # Implementation note:
        # this is currently done with AppleScript which takes ~300ms on M1 Mac
        # it's faster with ScriptingBridge (~80ms) but when adding via ScriptingBridge
        # the attachment sometimes is added twice
        # See #15 for more details

        # must pass fully resolved path to AppleScript
        path = pathlib.Path(path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        attachment_id = self._run_script("noteAddAttachment", str(path))
        return Attachment(self._note.attachments().objectWithID_(attachment_id))

    def show(self):
        """Show note in Notes.app UI"""
        self._run_script("noteShow")

    def asdict(self) -> dict[str, Any]:
        """Return dict representation of note"""
        return {
            "account": self.account,
            "id": self.id,
            "name": self.name,
            "body": self.body,
            "plaintext": self.plaintext,
            "creation_date": self.creation_date,
            "modification_date": self.modification_date,
            "password_protected": self.password_protected,
            "folder": self.folder,
        }

    def _run_script(self, script: str, *args):
        """Run AppleScript script"""
        return run_script(script, self.account, self.id, *args)

    def _parse_id_from_object(self) -> str:
        """Parse the ID from the object representation when it can't be determined by ScriptingBridge"""

        # there are some conditions (e.g. using selection on Catalina or using a predicate)
        # where the ScriptingBridge sets the object ID to 0
        # I haven't been able to figure out why but in this case, the id can be determined
        # by examining the string representation of the object which looks like this:
        # <SBObject @0x7fd721544690: <class ''> id "x-coredata://19B82A76-B3FE-4427-9C5E-5107C1E3CA57/IMAPNote/p87" of application "Notes" (55036)>
        if match := re.search(r'id "(x-coredata://.+?)"', str(self._note)):
            return match[1]
        return None

    def __repr__(self) -> str:
        return f"Note({self.id})"

    def __eq__(self, other: "Note"):
        return (self.id, self.account) == (other.id, other.account)

    def __hash__(self) -> int:
        return hash(repr(self))


class Attachment:
    """Notes.app Attachment object"""

    def __init__(self, attachment: ScriptingBridge.SBObject):
        self._attachment = attachment

    @cached_property
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


class Folder:
    """Folder object"""

    def __init__(self, folder: ScriptingBridge.SBObject):
        self._folder = folder

    @cached_property
    def id(self) -> str:
        """ID of folder"""
        return (
            str(folder_id)
            if (folder_id := self._folder.id())
            else str(parse_id_from_object(self._folder.get()))
        )

    @property
    def name(self) -> str:
        """Name of folder"""
        return str(self._folder.name())
