"""Python to AppleScript bridge for automating Notes.app on macOS"""

from ._version import __version__
from .errors import (
    AppleScriptError,
    ContentLossError,
    DatabaseUnavailableError,
    FolderNotFoundError,
    MacNotesAppError,
    NotesPermissionError,
    ScriptingBridgeError,
    UnsavedChangesError,
)
from .notesapp import Account, Folder, Note, NotesApp, NotesList
from .script_loader import check_automation_permission

__all__ = [
    "__version__",
    "Account",
    "AppleScriptError",
    "ContentLossError",
    "DatabaseUnavailableError",
    "Folder",
    "FolderNotFoundError",
    "MacNotesAppError",
    "Note",
    "NotesApp",
    "NotesList",
    "NotesPermissionError",
    "ScriptingBridgeError",
    "UnsavedChangesError",
    "check_automation_permission",
]
