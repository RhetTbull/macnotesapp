"""Entry point for macnotesapp CLI"""

import json
import os
import pathlib
import sys
from typing import Dict, Iterable

import click
import markdown2
import questionary
from applescript import ScriptError
from markdownify import markdownify as html2md
from rich.console import Console
from rich.markdown import Markdown

import macnotesapp
from macnotesapp import __version__
from macnotesapp import NotesList

from .cli_config import (
    CONFIG_FILE,
    DEFAULT_EDITOR,
    DEFAULT_FORMAT,
    FORMAT_HTML,
    FORMAT_MARKDOWN,
    FORMAT_OPTIONS,
    FORMAT_PLAINTEXT,
    ConfigSettings,
)
from .cli_help import RichHelpCommand, help
from .cli_param_types import URLType
from .readable import get_readable_html

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


@click.command(name="add", cls=RichHelpCommand)
@click.option("--show", "-s", is_flag=True, help="Show note in Notes after adding.")
@click.option("--file", "-F", required=False, type=click.File())
@click.option("--url", "-u", required=False, type=URLType())
@click.option("--html", "-h", is_flag=True, help="Use HTML for body of note.")
@click.option("--markdown", "-m", is_flag=True, help="Use Markdown for body of note.")
@click.option(
    "--plaintext",
    "-p",
    is_flag=True,
    help="Use plaintext for body of note (default unless changed in `notes config`).",
)
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
def add_note(
    show, file, url, html, markdown, plaintext, edit, account_name, folder_name, note
):
    """Add new note.

    There are multiple ways to add a new note:

    [i]Add a new note from standard input (STDIN)[/]:

    [b]notes add[/]

    [b]cat file.txt | notes add[/]

    [b]notes add < file.txt[/]

    [i]Add a new note by passing string on command line[/]:

    [b]notes add NOTE[/]

    [i]Add a new note by opening default editor (defined in $EDITOR or via `notes config`)[/]:

    [b]notes add --edit[/]

    [b]notes add -e[/]

    [i]Add a new note from URL (downloads URL, creates a cleaned readable version to store in new Note):

    [b]notes add --url URL

    [b]notes add -u URL

    If NOTE is a single line, adds new note with name NOTE and no body.
    If NOTE is more than one line, adds new note where name is first line of NOTE and body is remainder.

    Body of note must be plain text unless [i]--html/-h[/] or [i]--markdown/-m[/] flag is set
    in which case body should be HTML or Markdown, respectively.
    If [i]--edit/-e[/] flag is set, note will be opened in default editor before being added.
    If [i]--show/-s[/] flag is set, note will be shown in Notes.app after being added.

    Account and top level folder may be specified with [i]--account/-a[/] and [i]--folder/-f[/], respectively.
    If not provided, default account and folder are used.
    """

    if sum([html, markdown, plaintext]) > 1:
        click.echo(
            "Only one of --html, --markdown, and --plaintext can be specified.",
            err=True,
        )
        raise click.Abort()

    if file and url:
        click.echo("Only one of --file, --url can be specified.", err=True)
        raise click.Abort()

    config = ConfigSettings()
    format_ = config.format
    if html:
        format_ = FORMAT_HTML
    elif markdown:
        format_ = FORMAT_MARKDOWN
    elif plaintext:
        format_ = FORMAT_PLAINTEXT

    folder_name = folder_name or config.folder
    account_name = account_name or config.account
    editor = config.editor

    if file:
        note_text = file.read()
    elif url:
        try:
            name, body = get_readable_html(url)
            note_text = f"{name}\n{body}"
        except Exception as e:
            click.echo(f"Error downloading url '{url}': {e}.", err=True)
            raise click.Abort() from e
    elif note == "-" or (not note and not edit):
        note_text = sys.stdin.read()
    else:
        note_text = note

    if edit:
        ext = (
            ".html"
            if format_ == FORMAT_HTML
            else ".md"
            if format_ == FORMAT_MARKDOWN
            else ".txt"
        )
        note_text = click.edit(note_text, editor=editor, extension=ext)

    if not note_text:
        click.echo("No note text.", err=True)
        raise click.Abort()

    note_text = note_text.strip()
    note_parts = note_text.partition("\n")
    name, body = note_parts[0], note_parts[2]

    if format_ == FORMAT_MARKDOWN:
        # convert Markdown to HTML
        body = markdown2.markdown(body, extras=MARKDOWN_EXTRAS)
    elif format_ != FORMAT_HTML:
        # convert plain text to HTML
        body = "".join(f"<div>{line or '<br>'}</div>\n" for line in body.split("\n"))

    notes = macnotesapp.NotesApp()
    try:
        account = notes.account(account_name)
        new_note = account.make_note(name, body, folder_name)
        if show:
            new_note.show()
    except ScriptError as e:
        click.echo(f"Error adding note: {e}", err=True)
        raise click.Abort() from e


@click.command(name="list")
@click.option(
    "--account",
    "-a",
    "account_name",
    metavar="ACCOUNT",
    multiple=True,
    type=str,
    help="Limit results to account ACCOUNT; may be repeated to include multiple accounts.",
)
# @click.option(
#     "--folder",
#     "-f",
#     "folder_name",
#     metavar="FOLDER",
#     multiple=True,
#     type=str,
#     help="Limit results to folder FOLDER; may be repeated to include multiple folders.",
# )
@click.argument("text", metavar="TEXT", required=False)
def list_notes(account_name, text):
    """List notes, optionally filtering by account or text."""
    notesapp = macnotesapp.NotesApp()
    print_notes_list(
        notesapp.noteslist(
            accounts=[account_name] if account_name else None,
            text=[text] if text else None,
        )
    )


@click.command(name="cat")
@click.option("--plaintext", "-p", is_flag=True, help="Output note as plain text.")
@click.option("--markdown", "-m", is_flag=True, help="Output note as Markdown.")
@click.option("--html", "-h", is_flag=True, help="Output note as HTML.")
@click.option(
    "--json",
    "-j",
    "json_",
    is_flag=True,
    help="Output note as JSON. "
    "The default format for the note body in JSON is HTML "
    "(this is how the note is stored in Notes). "
    "If --plaintext or --markdown is also specified, "
    "the note body in the resulting JSON will be in the specified format.",
)
@click.argument("name", metavar="NOTE_NAME", required=True)
def cat_notes(name, plaintext, markdown, html, json_):
    """Print one or more notes to STDOUT"""
    notesapp = macnotesapp.NotesApp()
    notes = notesapp.notes(name=[name])
    output = (
        "plaintext"
        if plaintext
        else "markdown"
        if markdown
        else "html"
        if html
        else "rich"
    )

    if json_:
        print_notes_as_json(notes, plaintext=plaintext)
    else:
        for note in notes:
            print_note(note, output=output)


@click.command(name="config")
def config():
    """Configure default settings for account, editor, etc."""
    notes = macnotesapp.NotesApp()
    config = ConfigSettings()
    settings = config.read()

    # account
    accounts = notes.accounts
    account = settings.get("account")
    account = account if account and account in accounts else notes.default_account
    settings["account"] = questionary.select(
        "Select default account for new notes added with `notes add`: ",
        choices=accounts,
        default=account,
    ).ask()

    # folder
    account = notes.account(settings["account"])
    folders = account.folders
    folder = settings.get("folder")
    folder = folder if folder and folder in folders else account.default_folder
    settings["folder"] = questionary.select(
        "Select default folder for new notes: ", choices=folders, default=folder
    ).ask()

    # format
    format_ = settings.get("format")
    format_ = format_ if format_ and format_ in FORMAT_OPTIONS else DEFAULT_FORMAT
    settings["format"] = questionary.select(
        "Select default format for new notes: ", choices=FORMAT_OPTIONS, default=format_
    ).ask()

    # editor
    def validate_editor(env_or_path: str) -> bool:
        """Validate that env or path is valid for editor"""
        if not env_or_path.startswith("$"):
            return pathlib.Path(env_or_path).is_file()
        path = os.environ.get(env_or_path[1:])
        return bool(path and pathlib.Path(path).is_file())

    editor = settings.get("editor")
    editor = editor if editor and validate_editor(editor) else DEFAULT_EDITOR
    settings["editor"] = questionary.text(
        "Enter an environment variable (starting with '$') or full path to use for default editor: ",
        default=editor,
        validate=validate_editor,
    ).ask()
    config.write(settings)
    click.echo(f"Settings saved to {CONFIG_FILE}")


@click.command(name="dump")
@click.option("--selected", "-s", is_flag=True, help="Dump only selected notes.")
@click.option("--no-body", "-B", is_flag=True, help="Do not dump note body.")
def dump(selected, no_body):
    """Dump all notes or selection of notes for debugging"""
    notesapp = macnotesapp.NotesApp()
    if selected:
        for note in notesapp.selection:
            dump_note(note, no_body=no_body)
    else:
        for account in notesapp.accounts:
            noteslist = notesapp.noteslist(accounts=[account])
            dump_notes_list(noteslist, account)


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


# add the commands to the main group
for command in [accounts, add_note, cat_notes, config, list_notes, dump, help]:
    cli_main.add_command(command)


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


def print_notes_list(noteslist: NotesList):
    """Print note list to STDOUT"""
    folders = noteslist.folder
    names = noteslist.name
    body = noteslist.plaintext
    folder_len = max([len(f) for f in folders if f is not None] or [10])
    name_len = 30
    padding = 2
    console = Console()
    body_len = console.width - name_len - folder_len - padding * 3
    body_len = max(body_len, 30)
    format_str = (" " * padding).join(
        "{:<" + f"{x}" + "}" for x in [folder_len, name_len, body_len]
    )
    print(format_str.format("Folder", "Name", "Body"))
    for note in zip(folders, names, body):
        folder, name, body = note
        folder = folder or "---"
        name = name or "---"
        body = body or "---"
        name = (
            f"{name[:name_len-padding]}.." if len(name) > (name_len - padding) else name
        )
        body = body.replace("\n", " ")
        body = (
            f"{body[:body_len-padding]}.." if len(body) > (body_len - padding) else body
        )
        print(format_str.format(folder, name, body))


def print_note(note: macnotesapp.Note, output: str):
    """Print a note to STDOUT

    Args:
        note: Note to print
        output: Output format (plaintext, markdown, html, rich)
    """

    console = Console()
    # print note, not JSON
    if output == "plaintext":
        console.print(note.plaintext)
    elif output == "rich":
        console.print(Markdown(html2md(note.body)))
    elif output == "markdown":
        console.print(html2md(note.body))
    elif output == "html":
        console.print(note.body)


def print_notes_as_json(notes: Iterable[macnotesapp.Note], plaintext: bool = False):
    """Print notes as JSON to STDOUT

    Args:
        notes: Notes to print
        plaintext: If True, print plaintext of note body instead of HTML
    """

    json_list = []
    for note in notes:
        json_data = note.asdict()
        if plaintext:
            json_data["body"] = json_data["plaintext"]
        del json_data["plaintext"]
        json_data["creation_date"] = json_data["creation_date"].isoformat()
        json_data["modification_date"] = json_data["modification_date"].isoformat()
        json_list.append(json_data)
    console = Console()
    console.print(json.dumps(json_list, indent=4))


def dump_note(note: macnotesapp.Note, no_body: bool = False):
    """Dump note data to STDOUT for debugging purposes"""
    print(f"{note.id=}")
    print(f"{note.name=}")
    print(f"{note.account=}")
    print(f"{note.folder=}")
    print(f"{note.creation_date=}")
    print(f"{note.modification_date=}")
    print(f"{note.password_protected=}")
    if not no_body:
        print(f"{note.body=}")
        print(f"{note.plaintext=}")


def dump_notes_list(
    noteslist: macnotesapp.NotesList, account: str, no_body: bool = False
):
    """Dump NotesList data to STDOUT for debugging purposes"""
    notesdicts = noteslist.asdict()
    for notesdict in notesdicts:
        print(f"note.id={notesdict['id']}")
        print(f"note.name={notesdict['name']}")
        print(f"note.folder={notesdict['folder']}")
        print(f"note.account={account}")
        print(f"note.creation_date={notesdict['creation_date']}")
        print(f"note.modification_date={notesdict['modification_date']}")
        print(f"note.password_protected={notesdict['password_protected']}")
        if not no_body:
            print(f"note.body={notesdict['body']}")
            print(f"note.plaintext={notesdict['plaintext']}")
