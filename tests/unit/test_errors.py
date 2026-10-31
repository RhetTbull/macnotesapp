"""Test mapping of AppleScript errors to macnotesapp exceptions"""

import pytest
from applescript import ScriptError
from Foundation import NSAppleScriptErrorMessage, NSAppleScriptErrorNumber

import macnotesapp.script_loader as script_loader
from macnotesapp import NotesPermissionError


class FakeScript:
    def __init__(self, number):
        self.number = number

    def call(self, *args):
        raise ScriptError(
            {NSAppleScriptErrorNumber: self.number, NSAppleScriptErrorMessage: "nope"}
        )


@pytest.mark.parametrize("number", [-1743, -1744])
def test_permission_error(monkeypatch, number):
    monkeypatch.setattr(script_loader, "get_script", lambda: FakeScript(number))
    with pytest.raises(NotesPermissionError) as exc:
        script_loader.run_script("noteGetName", "iCloud", "x")
    # existing code that catches applescript.ScriptError still works
    assert isinstance(exc.value, ScriptError)
    assert exc.value.number == number
    assert "Automation" in str(exc.value)


def test_other_errors_unchanged(monkeypatch):
    monkeypatch.setattr(script_loader, "get_script", lambda: FakeScript(-1728))
    with pytest.raises(ScriptError) as exc:
        script_loader.run_script("noteGetName", "iCloud", "x")
    assert not isinstance(exc.value, NotesPermissionError)
    assert exc.value.number == -1728
