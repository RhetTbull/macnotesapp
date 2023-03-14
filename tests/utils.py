"""Utils for testing"""

from __future__ import annotations

import platform


def get_macos_version() -> tuple[int, int, int]:
    # returns tuple of ints containing OS version
    # e.g. 10.13.6 = (10, 13, 6)
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
    return (int(ver), int(major), int(minor))
