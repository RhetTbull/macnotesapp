"""Python to AppleScript bridge for automating Notes.app on macOS"""

from ._version import __version__
from .errors import (
    AppleScriptError,
    MacNotesAppError,
    NotesPermissionError,
    ScriptingBridgeError,
)
from .notesapp import Account, Folder, Note, NotesApp, NotesList
from .script_loader import check_automation_permission

__all__ = [
    "__version__",
    "Account",
    "AppleScriptError",
    "Folder",
    "MacNotesAppError",
    "Note",
    "NotesApp",
    "NotesList",
    "NotesPermissionError",
    "ScriptingBridgeError",
    "check_automation_permission",
]
