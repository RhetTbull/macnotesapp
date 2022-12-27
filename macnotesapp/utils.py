"""Utility functions for macnotesapp"""

import datetime

import Foundation


def NSDate_to_datetime(nsdate: Foundation.NSDate) -> datetime.datetime:
    """Convert NSDate to datetime.datetime"""
    return datetime.datetime.fromtimestamp(nsdate.timeIntervalSince1970())

def OSType(s: str):
    """Convert a string to an OSType"""
    return int.from_bytes(s.encode("UTF-8"), "big")
