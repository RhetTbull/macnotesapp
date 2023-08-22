"""Utility functions for macnotesapp"""

import datetime
import platform

import Foundation


def NSDate_to_datetime(nsdate: Foundation.NSDate) -> datetime.datetime:
    """Convert NSDate to datetime.datetime"""
    return datetime.datetime.fromtimestamp(nsdate.timeIntervalSince1970())


def OSType(s: str):
    """Convert a string to an OSType"""
    return int.from_bytes(s.encode("UTF-8"), "big")


def get_macos_version():
    # returns tuple of str containing OS version
    # e.g. 10.13.6 = ("10", "13", "6")
    version = platform.mac_ver()[0].split(".")
    if len(version) == 2:
        (ver, major) = version
        minor = "0"
    elif len(version) == 3:
        (ver, major, minor) = version
    else:
        raise (
            ValueError(
                f"Could not parse version string: {platform.mac_ver()} {version}"
            )
        )
    return (ver, major, minor)
