"""Test tiers for macnotesapp

- tests/unit: no Notes.app access; always run
- tests/integration: automated tests against Notes.app that only create, change, and
  delete notes inside temporary folders they create; run with --integration
- tests/manual: tests that prompt for input or change notes outside a temporary
  folder; run with --manual -s
"""

import pathlib

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        help="run integration tests against Notes.app "
        "(creates and deletes temporary folders in the default account)",
    )
    parser.addoption(
        "--manual",
        action="store_true",
        help="run manual tests that prompt for input or change notes "
        "outside a temporary folder (use with -s)",
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        parts = pathlib.Path(str(item.fspath)).parts
        if "integration" in parts:
            item.add_marker(pytest.mark.integration)
            if not config.getoption("--integration"):
                item.add_marker(pytest.mark.skip(reason="needs --integration"))
        elif "manual" in parts:
            item.add_marker(pytest.mark.manual)
            if not config.getoption("--manual"):
                item.add_marker(pytest.mark.skip(reason="needs --manual -s"))
