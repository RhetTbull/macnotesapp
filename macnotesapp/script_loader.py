"""Load and run the AppleScript handlers in macnotesapp.applescript"""

from __future__ import annotations

import functools
from importlib.resources import files

from applescript import AppleScript

from .logging import logger

SCRIPT_FILE = "macnotesapp.applescript"


def load_script_source() -> str:
    """Return the source of the AppleScript handlers"""
    return files(__package__).joinpath(SCRIPT_FILE).read_text(encoding="utf-8")


@functools.cache
def get_script() -> AppleScript:
    """Return the compiled AppleScript; compiled on first use and then cached"""
    logger.debug(f"Compiling {SCRIPT_FILE}")
    return AppleScript(load_script_source())


def run_script(name, *args):
    """Run AppleScript handler name with args"""
    logger.debug(f"Running script {name} with args {args}")
    return get_script().call(name, *args)
