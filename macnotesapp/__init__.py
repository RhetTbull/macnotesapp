"""Python to AppleScript bridge for automating Notes.app on macOS"""

from ._version import __version__
from .notesapp import Account, Folder, Note, NotesApp, NotesList

__all__ = ["Account", "Folder", "Note", "NotesApp", "NotesList"]
