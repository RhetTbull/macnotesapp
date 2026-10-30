"""Fake ScriptingBridge and macnotesapp objects for unit tests that don't use Notes.app"""

from __future__ import annotations

from datetime import datetime

import Foundation


class FakeSBContainer:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class FakeSBNote:
    """Stand-in for a ScriptingBridge note object; each property is a method"""

    def __init__(self, **props):
        self._props = props

    def __getattr__(self, name):
        try:
            value = self._props[name]
        except KeyError:
            raise AttributeError(name) from None
        return lambda: value

    def __str__(self):
        return "<SBObject @0x0: <class ''> of application \"Notes\">"


class FakeSBNotesArray(list):
    """Stand-in for an SBElementArray of notes with configurable bulk selector results"""

    def __init__(self, notes, bulk=None):
        super().__init__(notes)
        self._bulk = bulk or {}

    def arrayByApplyingSelector_(self, selector):
        if selector in self._bulk:
            return self._bulk[selector]
        return [getattr(note, selector)() for note in self]


def nsdate(dt: datetime):
    return Foundation.NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


class FakeNote:
    """Stand-in for macnotesapp.Note used by CLI tests"""

    def __init__(
        self, name, id, folder="Notes", account="iCloud", body="", attachments=()
    ):
        self.name = name
        self.id = id
        self.folder = folder
        self.account = account
        self.body = body
        self.attachments = list(attachments)
        self.modification_date = datetime(2026, 1, 2, 3, 4)
        self.deleted = False

    def delete(self):
        self.deleted = True

    def asdict(self):
        return {
            "account": self.account,
            "id": self.id,
            "name": self.name,
            "body": self.body,
            "plaintext": self.body,
            "creation_date": self.modification_date,
            "modification_date": self.modification_date,
            "password_protected": False,
            "folder": self.folder,
        }


class FakeNotesList:
    """Stand-in for macnotesapp.NotesList used by CLI tests"""

    def __init__(self, notes):
        self._notes = notes

    def asdict(self, body=True):
        records = [note.asdict() for note in self._notes]
        if not body:
            for record in records:
                del record["body"], record["plaintext"]
        return records


class FakeNotesApp:
    """Stand-in for macnotesapp.NotesApp that records how notes() was called"""

    def __init__(self, notes):
        self._notes = notes
        self.calls = []

    def noteslist(self, **kwargs):
        self.calls.append(kwargs)
        return FakeNotesList(self._notes)

    def notes(self, **kwargs):
        self.calls.append(kwargs)
        if ids := kwargs.get("id"):
            return [n for n in self._notes if n.id in ids]
        name = kwargs["name"][0].lower()
        if kwargs.get("exact_name"):
            return [n for n in self._notes if n.name.lower() == name]
        return [n for n in self._notes if name in n.name.lower()]
