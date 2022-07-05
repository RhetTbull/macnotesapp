"""Load applescript from file"""

from applescript import AppleScript

from .macnotesapp_applescript import NOTES_APPLESCRIPT

SCRIPT_OBJ = AppleScript(NOTES_APPLESCRIPT)


def run_script(name, *args):
    """Run function name contained in SCRIPT_OBJ"""
    return SCRIPT_OBJ.call(name, *args)
