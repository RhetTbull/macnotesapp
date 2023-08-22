"""Load applescript from file"""

import logging

from applescript import AppleScript

from .logging import logger
from .macnotesapp_applescript import NOTES_APPLESCRIPT

SCRIPT_OBJ = AppleScript(NOTES_APPLESCRIPT)


def run_script(name, *args):
    """Run function name contained in SCRIPT_OBJ"""
    # print(f"Running script {name} with args {args}")
    logger.debug(f"Running script {name} with args {args}")
    return SCRIPT_OBJ.call(name, *args)
