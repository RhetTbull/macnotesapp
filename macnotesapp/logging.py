"""Logging and debug module for macnotesapp"""

import logging

logging.basicConfig()
logger = logging.getLogger("macnotesapp")
logger.setLevel(logging.WARNING)


def set_debug(debug: bool):
    """Set logger level to debug"""
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)


def get_debug():
    """Return True if logger level is set to debug"""
    return logger.level == logging.DEBUG


__all__ = [
    "get_debug",
    "set_debug",
    "logger",
]
