"""Fixtures for integration tests: everything happens in temporary folders"""

import uuid

import pytest

from macnotesapp import Account, NotesApp, check_automation_permission


@pytest.fixture(scope="session")
def notesapp() -> NotesApp:
    check_automation_permission()
    return NotesApp()


@pytest.fixture(scope="session")
def account(notesapp) -> Account:
    """Default account; temporary folders are created here"""
    return notesapp.account()


@pytest.fixture(scope="session")
def run_id() -> str:
    """Unique ID for this test run, used in folder and note names"""
    return uuid.uuid4().hex[:8]


def _temp_folder(account: Account, name: str):
    account.make_folder(name)
    try:
        yield name
    finally:
        # deleting a folder moves its notes to Recently Deleted
        if name in account.folders:
            account.delete_folder(name)


@pytest.fixture(scope="session")
def sandbox(account, run_id):
    """Name of a temporary folder that is deleted at the end of the session"""
    yield from _temp_folder(account, f"macnotesapp-test-{run_id}")


@pytest.fixture(scope="session")
def sandbox2(account, run_id):
    """Second temporary folder, used as a destination for moves"""
    yield from _temp_folder(account, f"macnotesapp-test-{run_id}-2")


@pytest.fixture
def note_name(run_id, request) -> str:
    """Unique note name for a test"""
    return f"macnotesapp test {run_id} {request.node.name}"
