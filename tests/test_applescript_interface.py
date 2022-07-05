"""Test Python to AppleScript interface for macnotesapp """

import pytest

from macnotesapp import Account, Note, NotesApp


@pytest.fixture(scope="session")
def notes() -> NotesApp:
    return NotesApp()


def prompt(message):
    """Helper function for tests that require user input"""
    message = f"\n{message}\nPlease answer y/n: "
    answer = input(message)
    return answer.lower() == "y"


##### Test NotesApp #####


def test_notes_accounts(notes):
    """Test NotesApp.accounts"""
    accounts = notes.accounts
    assert prompt(f"Does Notes contain the following accounts: {accounts}?")


def test_notes_default_account(notes):
    """Test NotesApp.default_account"""
    default = notes.default_account
    assert prompt(f"Is default account {default}?")


def test_notes_len(notes):
    """Test NotesApp.__len__"""
    assert prompt(f"Are there {len(notes)} notes?")


def test_notes_notes(notes):
    """Test NotesApp.notes"""
    assert prompt(f"Are there {len(notes.notes)} notes?")


def test_notes_generator(notes):
    """Test NotesApp.__iter__"""
    all_notes = list(notes)
    assert prompt(f"Are there {len(all_notes)} notes?")


def test_notes_version(notes):
    """Test NotesApp.version"""
    assert prompt(f"Does Notes.app version = {notes.version}?")


def test_notes_selection_1(notes):
    """Test NotesApp.selection"""
    assert prompt("Select a single note.")
    assert prompt(f"Is the selected note named '{notes.selection[0].name}'?")


def test_notes_selection_2(notes):
    """Test NotesApp.selection"""
    assert prompt("Select two notes.")
    assert len(notes.selection) == 2


def test_notes_find_notes_name(notes):
    """Test NotesApp.find_notes"""
    name = input("\nPlease type a name of a note to search for: ")
    matches = notes.find_notes(name=name)
    assert prompt(
        f"Found {len(matches)} matching note(s) with name matching '{name}':"
        f"\n{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )


def test_notes_find_notes_body(notes):
    """Test NotesApp.find_notes"""
    text = input("\nPlease type text of a note to search for in body: ")
    matches = notes.find_notes(text=text)
    assert prompt(
        f"Found {len(matches)} matching note(s) with text '{text}' in body:\n"
        f"{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )


def test_notes_find_notes_name_and_body(notes):
    """Test NotesApp.find_notes"""
    text = input("\nPlease type text of a note to search for in name and body: ")
    matches = notes.find_notes(name=text, text=text)
    assert prompt(
        f"Found {len(matches)} matching note(s) with text '{text}' in body:\n"
        f"{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )


def test_notes_quit(notes):
    notes.quit()
    assert prompt("Did Notes.app quit?")


def test_notes_activate(notes):
    notes.activate()
    assert prompt("Did Notes.app activate?")


##### Test Account #####


def test_account(notes):
    """Test Account"""
    account_name = input(
        f"\nYou have the following Notes accounts: {notes.accounts}.\nPlease type name of account to use for test: "
    )
    account = Account(account_name)
    assert prompt(f"Is name of account '{account.name}'?")
    assert prompt(f"Is default folder of account '{account.default_folder}'?")
    assert prompt(f"Does account contain {len(account)} notes?")
    assert prompt(f"Does account contain {len(account.notes)} notes?")
    all_notes = list(account.notes)
    assert prompt(f"Does account contain {len(all_notes)} notes?")

    name = input(
        f"\nPlease type a name of a note to search for in account {account_name}: "
    )
    matches = account.find_notes(name=name)
    assert prompt(
        f"Found {len(matches)} matching note(s) with text '{name}' in name:\n"
        f"{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )

    text = input(
        f"\nPlease type a text of a note to search for in account {account_name}: "
    )
    matches = account.find_notes(text=text)
    assert prompt(
        f"Found {len(matches)} matching note(s) with text '{text}' in body:\n"
        f"{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )

    text = input(
        f"\nPlease type a text of a note to search both name and body for in account {account_name}: "
    )
    matches = account.find_notes(name=text, text=text)
    assert prompt(
        f"Found {len(matches)} matching note(s) with text '{text}' in body:\n"
        f"{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )

    assert prompt(
        f"After you press 'y' and Enter, Notes.app will show account {account_name}."
    )
    account.show()
    assert prompt(f"Did account {account_name} show in Notes.app?")


##### Test Note #####


def test_note(notes):
    """Test Note class"""
    assert prompt("Select a single note for testing")
    selection = notes.selection
    assert selection
    note = selection[0]
    assert prompt(f"Does note name = '{note.name}'")
    assert prompt(f"Does note.body = {note.body}?")
    assert prompt(f"Does note plain text = {note.plaintext}")
    assert prompt(f"Does note creation date = {note.creation_date.isoformat()}")
    assert prompt(f"Does note modification date = {note.modification_date.isoformat()}")
    assert prompt(f"Does note folder = {note.folder}")
    assert prompt(f"Does note password protection status = {note.password_protected}")

    prompt("\nSelect a different note then continue.")
    note.show()
    assert prompt(
        f"Did the original note you selected ({note.name}) show in Notes.app? "
    )
