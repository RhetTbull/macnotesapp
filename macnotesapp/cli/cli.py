"""Entry point for macnotesapp CLI"""

import json
import sys
from typing import Dict

import click
import markdown2
from applescript import ScriptError

import macnotesapp
from macnotesapp import __version__

from .cli_help import help

# extra features to support for Markdown to HTML conversion with markdown2
MARKDOWN_EXTRAS = ["fenced-code-blocks", "footnotes", "tables"]


@click.command(name="accounts")
@click.option(
    "--json", "-j", "json_", is_flag=True, help="Print output in JSON format."
)
def accounts(json_):
    """Print information about Notes accounts."""
    account_data = get_account_data()
    if json_:
        print(json.dumps(account_data))
    else:
        for account in account_data:
            print(f"{account}:")
            for k, v in account_data[account].items():
                print(f"  {k}: {v}")


@click.command(name="add")
@click.option("--show", "-s", is_flag=True, help="Show note in Notes after adding.")
@click.option("--file", "-F", required=False, type=click.File())
@click.option("--html", "-h", is_flag=True, help="Use HTML for body of note.")
@click.option("--markdown", "-m", is_flag=True, help="Use Markdown for body of note.")
@click.option(
    "--edit", "-e", is_flag=True, help="Edit note text before adding in default editor."
)
@click.option(
    "--account",
    "-a",
    "account_name",
    metavar="ACCOUNT",
    type=str,
    help="Add note to account ACCOUNT.",
)
@click.option(
    "--folder",
    "-f",
    "folder_name",
    metavar="FOLDER",
    type=str,
    help="Add note to folder FOLDER.",
)
@click.argument("note", metavar="NOTE", required=False, default="")
def add_note(show, file, html, markdown, edit, account_name, folder_name, note):
    """Add new note.

    There are multiple ways to add a new note:

    Add a new note by opening default editor (defined in $EDITOR or via `notes config`):

    notes add

    Add a new note by passing string on command line:

    notes add NOTE

    If NOTE is a single line, adds new note with name NOTE and no body.
    If NOTE is more than one line, adds new note where name is first line of NOTE and body is remainder.

    Add a new note from STDIN:

    notes add -

    Body of note must be plain text unless --html/-h or --markdown/-m flag is set
    in which case body should be HTML or Markdown, respectively.
    If --edit/-e flag is set, note will be opened in default editor before being added.
    If --show/-s flag is set, note will be shown in Notes.app after being added.

    Account and top level folder may be specified with --account/-a and --folder/-f, respectively.
    If not provided, default account and folder are used.
    """

    if html and markdown:
        click.echo(
            "Both --html and --markdown cannot be specified at the same time.", err=True
        )
        raise click.Abort()

    if file:
        note_text = file.read()
    elif note == "-" or (not note and not edit):
        note_text = sys.stdin.read()
    else:
        note_text = note

    if edit:
        ext = ".html" if html else ".md" if markdown else ".txt"
        note_text = click.edit(note_text, extension=ext)

    if not note_text:
        click.echo("No note text.", err=True)
        raise click.Abort()

    note_text = note_text.strip()
    note_parts = note_text.partition("\n")
    name, body = note_parts[0], note_parts[2]

    if markdown:
        # convert Markdown to HTML
        body = markdown2.markdown(body, extras=MARKDOWN_EXTRAS)
    elif not html:
        # convert plain text to HTML
        body = "".join(f"<div>{line or '<br>'}</div>\n" for line in body.split("\n"))

    notes = macnotesapp.NotesApp()
    try:
        if account_name or folder_name:
            account = notes.account(account_name)
            new_note = account.make_note(name, body, folder_name)
        else:
            new_note = notes.make_note(name, body)

        if show:
            new_note.show()
    except ScriptError as e:
        click.echo(f"Error adding note: {e}", err=True)
        raise click.Abort() from e


@click.command(name="config")
def config():
    """Configure default settings."""
    raise NotImplementedError()


# Click CLI object & context settings
class CLI_Obj:
    def __init__(self, debug=False, group=None):
        self.debug = debug
        self.group = group


CTX_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CTX_SETTINGS)
@click.option(
    "--debug",
    required=False,
    is_flag=True,
    help="Enable debug output",
    hidden=True,
)
@click.version_option(__version__, "--version", "-v")
@click.pass_context
def cli_main(ctx, debug):
    """notes: work with Apple Notes on the command line."""
    ctx.obj = CLI_Obj(group=cli_main)


def get_account_data() -> Dict:
    """Get dict of account data for Notes accounts"""
    notes = macnotesapp.NotesApp()
    accounts = notes.accounts
    account_data = {}
    for account_name in accounts:
        account = notes.account(account_name)
        account_data[account_name] = {
            "id": account.id,
            "name": account_name,
            "notes_count": len(account),
            "default_folder": account.default_folder,
        }
    return account_data


for command in [accounts, add_note, config, help]:
    cli_main.add_command(command)
