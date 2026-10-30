"""Python interface to macOS Notes.app"""

from __future__ import annotations

import html
import os
import pathlib
import re
from collections.abc import Generator
from datetime import datetime
from functools import cached_property
from typing import Any

import AppKit
import applescript
import Foundation
import ScriptingBridge

from .errors import AppleScriptError, ScriptingBridgeError
from .script_loader import run_script
from .utils import NSDate_to_datetime, OSType, get_macos_version

# Note: string values returned from ScriptingBridge are PyObjC unicode objects and must
# be cast to str to ensure they work correctly with other functions


MAC_OS_VERSION = int(get_macos_version()[0])


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


def notes_predicate(
    name: list[str] | None = None,
    body: list[str] | None = None,
    text: list[str] | None = None,
    password_protected: bool | None = None,
    id: list[str] | None = None,
    exact_name: bool = False,
) -> AppKit.NSPredicate | None:
    """Build an NSPredicate to filter notes by property; returns None if no filters given.

    Values within a property are OR'd together; properties are AND'd together.
    If exact_name is True, name must match exactly (case-insensitive) instead of
    containing the search string.
    """
    format_strings = []
    args = []
    if name:
        op = "==[c]" if exact_name else "contains[cd]"
        format_strings.append([f"(name {op} %@)"] * len(name))
        args.extend(name)
    if body:
        format_strings.append(["(plaintext contains[cd] %@)"] * len(body))
        args.extend(body)
    if text:
        format_strings.append(
            ["(name contains[cd] %@)"] * len(text)
            + ["(plaintext contains[cd] %@)"] * len(text)
        )
        args.extend(text * 2)
    if password_protected is not None:
        format_strings.append(
            ["(passwordProtected == TRUE)"]
            if password_protected
            else ["(passwordProtected == FALSE)"]
        )
    if id:
        format_strings.append(["(id == %@)"] * len(id))
        args.extend(id)
    if not format_strings:
        return None
    or_strings = [" OR ".join(strings) for strings in format_strings]
    format_str = "(" + ") AND (".join(or_strings) + ")"
    return AppKit.NSPredicate.predicateWithFormat_argumentArray_(format_str, args)


def filter_accounts(
    account_list: ScriptingBridge.SBElementArray, accounts: list[str] | None
) -> ScriptingBridge.SBElementArray:
    """Filter SBElementArray of accounts to those whose name is in accounts"""
    if not accounts:
        return account_list
    # ScriptingBridge doesn't support "name IN %@" (silently matches nothing) so use OR
    format_str = " OR ".join(["name == %@"] * len(accounts))
    predicate = AppKit.NSPredicate.predicateWithFormat_argumentArray_(
        format_str, list(accounts)
    )
    return account_list.filteredArrayUsingPredicate_(predicate)


def title_html(name: str) -> str:
    """Return HTML for the title line of a note"""
    return f"<div><h1>{html.escape(name, quote=False)}</h1></div>\n"


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
        return [str(a.name()) for a in self._app.accounts()]

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
        exact_name: bool = False,
    ) -> list[Note]:
        """Return Note object for all notes contained in Notes.app or notes filtered by property.

        Args:
            name: list of note names to filter by
            body: list of note bodies to filter by
            text: list of note text to filter by
            password_protected: filter by password protected notes
            id: list of note ids to filter by
            accounts: list of account names to filter by
            exact_name: if True, name must match exactly (case-insensitive) instead of containing the search string

        Returns:
            list of Note objects
        """
        # TODO: should this be a generator?
        account_list = filter_accounts(self.app.accounts(), accounts)
        notes = []
        for account in account_list:
            notes.extend(
                Account(account).notes(
                    name, body, text, password_protected, id, exact_name=exact_name
                )
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
        exact_name: bool = False,
    ) -> NotesList:
        """Return NoteList object for all notes contained in account or notes filtered by property.

        Args:
            name: list of note names to filter by
            body: list of note bodies to filter by
            text: list of note text to filter by
            password_protected: filter by password protected notes
            id: list of note ids to filter by
            accounts: list of account names to filter by
            exact_name: if True, name must match exactly (case-insensitive) instead of containing the search string

        Returns:
            NotesList object
        """
        account_list = [
            Account(account)
            for account in filter_accounts(self.app.accounts(), accounts)
        ]
        noteslists = [
            account._noteslist(
                name=name,
                body=body,
                text=text,
                password_protected=password_protected,
                id=id,
                exact_name=exact_name,
            )
            for account in account_list
        ]
        return NotesList(*noteslists, accounts=[a.name for a in account_list])

    @property
    def selection(self) -> list[Note]:
        """Return lit of Note objects for selected notes"""
        notes = self.app.selection()
        return [Note(note) for note in notes]

    @property
    def version(self) -> str:
        """Return version of Notes.app"""
        return str(self.app.version())

    def make_note(
        self,
        name: str,
        body: str,
        attachments: list[str] | None = None,
        *,
        folder: str | None = None,
    ) -> Note:
        """Create new note in default account.

        Args:
            name: name of note; will be escaped for HTML
            body: body of note as HTML text
            attachments: optional list of paths to attachments to add to note
            folder: optional folder to create note in; if None, uses default folder

        Returns:
            newly created Note object
        """
        account = Account(self.app.defaultAccount())
        return account.make_note(name, body, folder=folder, attachments=attachments)

    def account(self, account: str | None = None) -> Account:
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

    def __iter__(self) -> Generator[Note, None, None]:
        """Generator to yield Note object for all notes contained in Notes.app"""
        for account in self.app.accounts():
            account_name = str(account.name())
            for note in account.notes():
                yield Note(note, account=account_name)


class Account:
    """Notes.app Account object"""

    def __init__(self, account: ScriptingBridge.SBObject):
        """Initialize Account object"""
        self._account = account

    @property
    def name(self) -> str:
        """Return name of account"""
        return str(self._account.name())

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
            return str(default_folder.name())
        return str(self._run_script("accountGetDefaultFolder"))

    @cached_property
    def id(self) -> str:
        """Return ID of account"""
        if id_ := self._account.id():
            return str(id_)
        return str(self._run_script("accountID"))

    def notes(
        self,
        name: list[str] | None = None,
        body: list[str] | None = None,
        text: list[str] | None = None,
        password_protected: bool | None = None,
        id: list[str] | None = None,
        exact_name: bool = False,
    ) -> list[Note]:
        """Return Note object for all notes contained in account or notes filtered by property.

        Args:
            name: list of note names to filter by
            body: list of note bodies to filter by
            text: list of note text to filter by
            password_protected: filter by password protected notes
            id: list of note ids to filter by
            exact_name: if True, name must match exactly (case-insensitive) instead of containing the search string

        Returns:
            list of Note objects
        """
        # TODO: should this be a generator?
        notes = self._noteslist(name, body, text, password_protected, id, exact_name)
        account_name = self.name
        return [Note(note, account=account_name) for note in notes.get()]

    def noteslist(
        self,
        name: list[str] | None = None,
        body: list[str] | None = None,
        text: list[str] | None = None,
        password_protected: bool | None = None,
        id: list[str] | None = None,
        exact_name: bool = False,
    ) -> NotesList:
        """Return NoteList object for all notes contained in account or notes filtered by property.

        Args:
            name: list of note names to filter by
            body: list of note bodies to filter by
            text: list of note text to filter by
            password_protected: filter by password protected notes
            id: list of note ids to filter by
            exact_name: if True, name must match exactly (case-insensitive) instead of containing the search string

        Returns:
            NotesList object"""
        notes = self._noteslist(name, body, text, password_protected, id, exact_name)
        return NotesList(notes, accounts=[self.name])

    def folder(self, folder: str) -> Folder:
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
    ) -> Note:
        """Create new note in account

        Args:
            name: name of note; will be escaped for HTML
            body: body of note as HTML text
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
            "body": f"{title_html(name)}{body}",
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

        new_note = Note(note, account=self.name)
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
        exact_name: bool = False,
    ) -> ScriptingBridge.SBElementArray:
        """Return SBElementArray for all notes contained in account or notes filtered by property"""
        notes = self._account.notes()
        predicate = notes_predicate(
            name, body, text, password_protected, id, exact_name=exact_name
        )
        if predicate is not None and notes:
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

    def make_folder(self, folder_name: str) -> Folder:
        """Create a new folder in this account.

        Args:
            folder_name: name for the new folder

        Returns:
            Folder object for the new folder
        """
        run_script("folderCreate", self.name, folder_name)
        return self.folder(folder_name)

    def delete_folder(self, folder_name: str):
        """Delete a folder from this account.

        Args:
            folder_name: name of folder to delete
        """
        run_script("folderDelete", self.name, folder_name)

    def __len__(self) -> int:
        """Return count of notes"""
        return len(self._account.notes())

    def __iter__(self) -> Generator[Note, None, None]:
        """Generator to yield all notes contained in Notes.app"""
        account_name = self.name
        for note in self._account.notes():
            yield Note(note, account=account_name)


class NotesList:
    """NotesList object for list of notes.
    Represents an SBElementArray of notes as returned by noteslist()
    """

    def __init__(
        self,
        *noteslist: ScriptingBridge.SBElementArray,
        accounts: list[str] | None = None,
    ):
        """Create NotesList

        Args:
            *noteslist: one SBElementArray of notes per account
            accounts: optional name of the account for each SBElementArray
        """
        self._noteslist = noteslist
        self._accounts = accounts or [None] * len(noteslist)

    @property
    def account(self) -> list[str | None]:
        """Return account name of every note in list (None if not known)"""
        return [
            account
            for noteslist, account in zip(self._noteslist, self._accounts, strict=True)
            for _ in range(len(noteslist))
        ]

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

    def asdict(self, body: bool = True) -> list[dict[str, Any]]:
        """Return list of dict representations of notes

        Args:
            body: if False, don't include body and plaintext (faster for large lists)
        """
        fields = {
            "account": self.account,
            "id": self.id,
            "name": self.name,
        }
        if body:
            fields["body"] = self.body
            fields["plaintext"] = self.plaintext
        fields |= {
            "creation_date": self.creation_date,
            "modification_date": self.modification_date,
            "password_protected": self.password_protected,
            "folder": self.container,
        }
        # strict: every field must have exactly one value per note
        return [
            dict(zip(fields, values, strict=True))
            for values in zip(*fields.values(), strict=True)
        ]

    def _apply_selector(self, selector) -> list[Any]:
        """Return note property for every note in list by applying selector

        Results are always aligned with the notes in the list: one value per note.
        """
        results_list = []
        for noteslist in self._noteslist:
            results = noteslist.arrayByApplyingSelector_(selector)
            count = len(noteslist)
            if results is None or len(results) != count:
                # bulk fetch failed or is incomplete (seen with body/plaintext on some
                # macOS versions); fall back to fetching from each note so values stay
                # aligned with the notes
                results = [getattr(note, selector)() for note in noteslist]
            results_list.extend(self._convert_value(selector, r) for r in results)
        return results_list

    @staticmethod
    def _convert_value(selector: str, value: Any) -> Any:
        """Convert a value returned by ScriptingBridge to a Python value"""
        # bulk results use NSNull for missing values
        if value is None or isinstance(value, Foundation.NSNull):
            return "" if selector in ["name", "body", "plaintext"] else None
        if selector in ["creationDate", "modificationDate"]:
            return NSDate_to_datetime(value)
        if selector == "container":
            return str(name) if (name := value.name()) else None
        if selector == "passwordProtected":
            return bool(value)
        return str(value)

    def __len__(self) -> int:
        """Return count of notes in list"""
        return len(self.id)


class Note:
    """Note object representing a note in Notes.app"""

    def __init__(self, note: ScriptingBridge.SBObject, account: str | None = None):
        """Initialize Note object

        Args:
            note: ScriptingBridge note object
            account: name of account the note belongs to, if known;
                if None, it will be looked up (slowly) via AppleScript when needed
        """
        self._note = note
        self._account_name = account

    @cached_property
    def account(self) -> str:
        """Return name of account note belongs to."""
        if self._account_name:
            return self._account_name
        # can't determine this easily from the note object
        # so use AppleScript
        return str(run_script("noteGetAccount", self.id))

    @cached_property
    def id(self) -> str:
        """Return note ID"""
        if note_id := self._note.id():
            return str(note_id)
        # if note object created from selection or predicate it may show ID of 0
        # but the ID is in the string representation of the object so parse it
        if note_id := parse_id_from_object(self._note):
            return note_id
        raise ScriptingBridgeError(f"Could not determine ID for note {self._note}")

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
        # return self._note.passwordProtected() # returns False even when note is password protected on some OS versions
        if MAC_OS_VERSION >= 13:
            return bool(self._note.passwordProtected())
        return bool(self._run_script("noteGetPasswordProtected"))

    @property
    def folder(self) -> str:
        """Return name of folder note is contained in"""
        # calling container() method on note object returns None
        # in many cases, so fall back to AppleScript
        if (container := self._note.container()) and (name := container.name()):
            return str(name)
        return str(self._run_script("noteGetContainer"))

    @property
    def attachments(self) -> list[Attachment]:
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

    def add_attachment(self, path: str | os.PathLike) -> Attachment:
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

        # must pass fully resolved path to attachment
        path = pathlib.Path(path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        try:
            attachment_id = self._run_script("noteAddAttachment", str(path))
        except applescript.ScriptError as e:
            attachment_id = parse_id_from_error(str(e))
        if not attachment_id:
            raise AppleScriptError(
                f"Could not get attachment id for attachment at path {path}"
            )
        return Attachment(self._note.attachments().objectWithID_(attachment_id))

    def show(self):
        """Show note in Notes.app UI"""
        self._run_script("noteShow")

    def delete(self):
        """Delete this note from Notes.app"""
        run_script("noteDelete", self.id)

    def move(self, folder_name: str):
        """Move this note to a different folder.

        Args:
            folder_name: name of folder to move note to
        """
        run_script("noteMove", self.id, folder_name, self.account)

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

    def __repr__(self) -> str:
        return f"Note({self.id})"

    def __eq__(self, other: object) -> bool:
        # note IDs are globally unique so no need to compare account
        if not isinstance(other, Note):
            return NotImplemented
        return self.id == other.id

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

        # name may be None for some attachments so fall back to last part of the ID
        filename = self.name or self.id.rsplit("/", 1)[-1]
        url = AppKit.NSURL.alloc().initFileURLWithPath_(
            os.path.join(str(path), filename)
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


def parse_id_from_error(error: str) -> str | None:
    """Parse the ID from the object representation from an AppleScript error"""
    # there are cases where AppleScript returns an error such as:
    # applescript.ScriptError: Notes got an error: Can’t get attachment id "x-coredata://5A2C18B7-767B-41A9-BF71-E4E966775D32/ICAttachment/p5631". (-1728) app='Notes' range=8198-8200
    if match := re.search(r'id "(x-coredata://.+?)"', str(error)):
        return match[1]
    return None
