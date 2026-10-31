"""Fixtures for integration tests: everything happens in temporary folders"""

import uuid

import pytest

from macnotesapp import Account, NotesApp, check_automation_permission
from macnotesapp.database import NotesDatabase
from macnotesapp.errors import DatabaseUnavailableError


@pytest.fixture(scope="session", params=["database", "scriptingbridge"])
def backend(request) -> str:
    """Run every test reading notes from the Notes database and from ScriptingBridge"""
    if request.param == "database":
        try:
            NotesDatabase().close()
        except DatabaseUnavailableError as e:
            pytest.skip(f"Notes database not readable: {e}")
    return request.param


@pytest.fixture(scope="session", autouse=True)
def unsaved_changes_file(tmp_path_factory):
    """Keep the CLI's record of unsaved changes out of the user's state directory"""
    from macnotesapp.cli import cli

    original = cli.UNSAVED_CHANGES_FILE
    cli.UNSAVED_CHANGES_FILE = tmp_path_factory.mktemp("state") / "unsaved.json"
    yield
    cli.UNSAVED_CHANGES_FILE = original


@pytest.fixture(scope="session")
def notesapp(backend) -> NotesApp:
    check_automation_permission()
    return NotesApp(backend=backend)


@pytest.fixture(scope="session")
def account(notesapp) -> Account:
    """Default account; temporary folders are created here"""
    return notesapp.account()


@pytest.fixture(scope="session")
def run_id(backend) -> str:
    """Unique ID for this test run and backend, used in folder and note names.

    Each backend gets its own folders and notes: pytest may set up both backends'
    fixtures at the same time, and Notes allows two folders with the same name.
    """
    return f"{uuid.uuid4().hex[:8]}-{'db' if backend == 'database' else 'sb'}"


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
    """Unique note name for a test.

    Kept short: Notes truncates names of more than about 67 characters with "…".
    """
    return f"macnotesapp test {run_id} {request.node.originalname}"
