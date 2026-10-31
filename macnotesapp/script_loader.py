"""Load and run the AppleScript handlers in macnotesapp.applescript"""

from __future__ import annotations

import functools
from importlib.resources import files

from applescript import AppleScript, ScriptError

from .errors import PERMISSION_ERRORS, NotesPermissionError
from .logging import logger

SCRIPT_FILE = "macnotesapp.applescript"

# sends an Apple Event to Notes so fails if the process isn't allowed to automate Notes
PERMISSION_CHECK_SCRIPT = 'tell application id "com.apple.Notes" to count accounts'

_permission_granted = False


def load_script_source() -> str:
    """Return the source of the AppleScript handlers"""
    return files(__package__).joinpath(SCRIPT_FILE).read_text(encoding="utf-8")


@functools.cache
def get_script() -> AppleScript:
    """Return the compiled AppleScript; compiled on first use and then cached"""
    logger.debug(f"Compiling {SCRIPT_FILE}")
    return AppleScript(load_script_source())


def run_script(name, *args):
    """Run AppleScript handler name with args

    Raises:
        NotesPermissionError: if the process is not allowed to automate Notes.app
        applescript.ScriptError: for any other AppleScript error
    """
    logger.debug(f"Running script {name} with args {args}")
    try:
        return get_script().call(name, *args)
    except ScriptError as e:
        if e.number in PERMISSION_ERRORS:
            raise NotesPermissionError(e._errorinfo) from e
        raise


def check_automation_permission() -> None:
    """Check that this process may automate Notes.app.

    macOS asks the user the first time; once permission is confirmed the check isn't repeated.
    ScriptingBridge calls fail silently (returning None) without permission,
    so call this before using NotesApp when a clear error is needed.

    Raises:
        NotesPermissionError: if permission is denied
    """
    global _permission_granted
    if _permission_granted:
        return
    try:
        AppleScript(PERMISSION_CHECK_SCRIPT).run()
    except ScriptError as e:
        if e.number in PERMISSION_ERRORS:
            raise NotesPermissionError(e._errorinfo) from e
        raise
    _permission_granted = True
