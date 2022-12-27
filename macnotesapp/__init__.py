"""Python to AppleScript bridge for automating Notes.app on macOS"""

from ._version import __version__
from .notesapp import Account, Note, NotesApp

__all__ = ["Account", "Note", "NotesApp"]
