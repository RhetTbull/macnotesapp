"""Test Python to AppleScript interface for macnotesapp """

import pytest
import questionary

from macnotesapp import Account, Note, NotesApp

from .utils import get_macos_version

ATTACHMENT_PATH = "tests/attachment.txt"


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


def test_notes_account(notes):
    """Test NotesApp.account()"""
    account = notes.account()
    assert prompt(f"Is default account {account.name}?")


def test_notes_account_with_name(notes):
    """Test NotesApp.account(account_name)"""
    account_name = notes.accounts[0]
    account = notes.account(account_name)
    assert isinstance(account, Account)
    assert account.name == account_name


def test_notes_len(notes):
    """Test NotesApp.__len__"""
    assert prompt(f"Are there {len(notes)} notes?")


def test_notes_notes(notes):
    """Test NotesApp.notes"""
    assert prompt(f"Are there {len(notes.notes())} notes?")


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
    """Test NotesApp.notes() with filter criteria"""
    name = input("\nPlease type a name of a note to search for: ")
    matches = notes.notes(name=[name])
    assert prompt(
        f"Found {len(matches)} matching note(s) with name matching '{name}':"
        f"\n{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )


def test_notes_find_notes_body(notes):
    """Test NotesApp.notes() with filter criteria"""
    text = input("\nPlease type text of a note to search for in body: ")
    matches = notes.notes(body=[text])
    assert prompt(
        f"Found {len(matches)} matching note(s) with text '{text}' in body:\n"
        f"{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )


def test_notes_find_notes_text(notes):
    """Test NotesApp.notes() with filter criteria"""
    text = input("\nPlease type text of a note to search for in name and body: ")
    matches = notes.notes(text=[text])
    assert prompt(
        f"Found {len(matches)} matching note(s) with text '{text}' in body:\n"
        f"{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )


def test_notes_make_note(notes):
    """Test NotesApp.make_note"""
    print("This test will make a new note in the default account.")
    name = input("\nPlease type name of note to make: ")
    body = input("\nPlease type body of note to make: ")
    note = notes.make_note(name=name, body=body)
    assert prompt(f"Was a new note named '{name}' created in default account?")


@pytest.mark.skipif(get_macos_version() < (13, 0, 0), reason="Requires macOS 13.0 or higher")
def test_notes_make_note_with_attachment(notes):
    """Test NotesApp.make_note"""
    print("This test will make a new note in the default account.")
    name = "Note with attachment"
    body = "This note has an attachment. #macnotesapp<br>"
    attachment = ATTACHMENT_PATH
    note = notes.make_note(name=name, body=body, attachments=[attachment])
    assert prompt(
        f"Was a new note named '{name}' created in default account with attachment?"
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
    account_name = questionary.select(
        "\nPlease select name of account to use for test: ",
        choices=notes.accounts,
        default=notes.default_account,
    ).ask()
    account = notes.account(account_name)
    assert prompt(f"Is name of account '{account.name}'?")
    assert prompt(f"Is default folder of account '{account.default_folder}'?")
    assert prompt(f"Does account contain {len(account)} notes?")
    assert prompt(f"Does account contain {len(account.notes())} notes?")
    assert prompt(f"Does account contain {account.folders} folders?")

    name = input(
        f"\nPlease type a name of a note to search for in account {account_name}: "
    )
    matches = account.notes(name=[name])
    assert prompt(
        f"Found {len(matches)} matching note(s) with text '{name}' in name:\n"
        f"{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )

    text = input(
        f"\nPlease type a body text of a note to search for in account {account_name}: "
    )
    matches = account.notes(text=[text])
    assert prompt(
        f"Found {len(matches)} matching note(s) with text '{text}' in body:\n"
        f"{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )

    text = input(
        f"\nPlease type a text of a note to search both name and body for in account {account_name}: "
    )
    matches = account.notes(name=[text], body=[text])
    assert prompt(
        f"Found {len(matches)} matching note(s) with text '{text}' in body:\n"
        f"{chr(10).join([f'- {note.name}' for note in matches])}.\n\nIs this correct?"
    )

    assert prompt(
        f"After you press 'y' and Enter, Notes.app will show account {account_name}."
    )
    account.show()
    assert prompt(f"Did account {account_name} show in Notes.app?")


def test_account_make_note(notes):
    """Test Account.make_note"""
    print("\nThis test will make a new note in an account you choose.")
    account_name = questionary.select(
        "\nPlease select name of account to use for test: ",
        choices=notes.accounts,
        default=notes.default_account,
    ).ask()
    account = notes.account(account_name)
    name = input("\nPlease type name of note to make: ")
    body = input("\nPlease type body of note to make: ")
    note = account.make_note(name=name, body=body)
    assert prompt(f"Was a new note named '{name}' created in account '{account.name}'?")


def test_account_make_note_in_folder(notes):
    """Test Account.make_note in a folder"""
    print("\nThis test will make a new note in an account and folder you choose.")
    account_name = questionary.select(
        "\nPlease select name of account to use for test: ",
        choices=notes.accounts,
        default=notes.default_account,
    ).ask()
    account = notes.account(account_name)
    folder = questionary.select(
        "\nPlease select name of folder to use for test: ",
        choices=account.folders,
        default=account.default_folder,
    ).ask()
    name = input("\nPlease type name of note to make: ")
    body = input("\nPlease type body of note to make: ")
    note = account.make_note(name=name, body=body, folder=folder)
    assert prompt(
        f"Was a new note named '{name}' created in folder '{folder}' of account '{account.name}'?"
    )


##### Test Note #####


def test_note(notes):
    """Test Note class"""
    assert prompt("Select a single note for testing")
    selection = notes.selection
    assert selection
    note = selection[0]
    assert prompt(f"Does note account = '{note.account}'?")
    assert prompt(f"Does note name = '{note.name}'?")
    assert prompt(f"Does note.body = '{note.body}'?")
    assert prompt(f"Does note plain text = '{note.plaintext}'?")
    assert prompt(f"Does note creation date = {note.creation_date.isoformat()}?")
    assert prompt(
        f"Does note modification date = {note.modification_date.isoformat()}?"
    )
    assert prompt(f"Does note folder = '{note.folder}'?")
    assert prompt(f"Does note password protection status = {note.password_protected}?")

    prompt("\nSelect a different note then continue.")
    note.show()
    assert prompt(
        f"Did the original note you selected ({note.name}) show in Notes.app? "
    )


def test_note_set_name(notes):
    """Test Note.name setter"""
    assert prompt("Select a note for testing that can be renamed")
    selection = notes.selection
    assert selection
    note = selection[0]
    old_name = note.name
    new_name = input(
        f"\nEnter new name for note that is currently named '{old_name}': "
    )
    note.name = new_name
    assert prompt(f"Was note '{old_name}' renamed to '{new_name}'?")


def test_note_set_body(notes):
    """Test Note.body setter"""
    assert prompt("Select a note for testing that can be changed")
    selection = notes.selection
    assert selection
    note = selection[0]
    old_body = note.body
    new_body = input(f"\nEnter new body for note named '{note.name}': ")
    note.body = new_body
    assert prompt(f"Was note body for note '{note.name}' changed to '{new_body}'?")
