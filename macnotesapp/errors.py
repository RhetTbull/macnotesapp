"""Exceptions raised by macnotesapp"""

from __future__ import annotations

from applescript import ScriptError

# AppleScript error numbers
ERR_AE_EVENT_NOT_PERMITTED = -1743
ERR_AE_EVENT_WOULD_REQUIRE_USER_CONSENT = -1744
PERMISSION_ERRORS = (
    ERR_AE_EVENT_NOT_PERMITTED,
    ERR_AE_EVENT_WOULD_REQUIRE_USER_CONSENT,
)


class MacNotesAppError(Exception):
    """Base class for macnotesapp errors"""


class AppleScriptError(MacNotesAppError):
    """Error raised when AppleScript fails to execute"""

    def __init__(self, *message):
        super().__init__(*message)


class ScriptingBridgeError(MacNotesAppError):
    """Errors raised when ScriptingBridge fails to execute"""

    def __init__(self, *message):
        super().__init__(*message)


class NotesPermissionError(MacNotesAppError, ScriptError):
    """The process is not allowed to automate Notes.app.

    Grant permission in System Settings > Privacy & Security > Automation.
    Subclasses applescript.ScriptError so existing handlers for ScriptError still catch it.
    """

    def __init__(self, errorinfo: dict | None = None):
        ScriptError.__init__(self, errorinfo or {})

    def __str__(self) -> str:
        return (
            "Not allowed to control Notes.app. Allow your terminal (or the app running "
            "Python) to control Notes in System Settings > Privacy & Security > "
            "Automation, then try again."
        )
