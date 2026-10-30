"""Entry point for macnotesapp CLI"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from collections.abc import Iterable
from datetime import datetime

import click
from rich.console import Console
from rich.markdown import Markdown

import macnotesapp
from macnotesapp import NotesList, __version__
from macnotesapp.errors import NotesPermissionError
from macnotesapp.formatting import (
    html_to_markdown,
    markdown_lossy_features,
    markdown_to_html,
    text_to_html,
)
from macnotesapp.logging import get_debug, set_debug
from macnotesapp.notesapp import title_html
from macnotesapp.script_loader import check_automation_permission

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

# exit codes; click uses 1 for ClickException and 2 for UsageError
EXIT_NOT_FOUND = 3


class NotFoundError(click.ClickException):
    """A note, folder, or account was not found"""

    exit_code = EXIT_NOT_FOUND


def get_notes_app() -> macnotesapp.NotesApp:
    """Return NotesApp after checking that this process may automate Notes.app"""
    check_automation_permission()
    return macnotesapp.NotesApp()


def isoformat(dt: datetime | None) -> str | None:
    """Return datetime as ISO 8601 string including the local UTC offset"""
    return dt.astimezone().isoformat() if dt else None


@click.command(name="accounts")
@click.option(
    "--json", "-j", "json_", is_flag=True, help="Print output in JSON format."
)
def accounts(json_):
    """Print information about Notes accounts."""
    account_data = get_account_data()
    if json_:
        click.echo(json.dumps(account_data))
    else:
        for account in account_data:
            click.echo(f"{account}:")
            for k, v in account_data[account].items():
                click.echo(f"  {k}: {v}")


@click.command(name="add", cls=RichHelpCommand)
@click.option("--show", "-s", is_flag=True, help="Show note in Notes after adding.")
@click.option("--file", "-F", required=False, type=click.File())
@click.option("--url", "-u", required=False, type=URLType())
@click.option("--html", "-H", is_flag=True, help="Use HTML for body of note.")
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

    Body of note must be plain text unless [i]--html/-H[/] or [i]--markdown/-m[/] flag is set
    in which case body should be HTML or Markdown, respectively.
    If [i]--edit/-e[/] flag is set, note will be opened in default editor before being added.
    If [i]--show/-s[/] flag is set, note will be shown in Notes.app after being added.

    Account and top level folder may be specified with [i]--account/-a[/] and [i]--folder/-f[/], respectively.
    If not provided, default account and folder are used.
    """

    if sum([html, markdown, plaintext]) > 1:
        raise click.UsageError(
            "Only one of --html, --markdown, and --plaintext can be specified."
        )

    if file and url:
        raise click.UsageError("Only one of --file, --url can be specified.")

    notes = get_notes_app()
    config = ConfigSettings()
    format_ = config.format
    if html:
        format_ = FORMAT_HTML
    elif markdown:
        format_ = FORMAT_MARKDOWN
    elif plaintext:
        format_ = FORMAT_PLAINTEXT

    # use the configured folder only for the configured account;
    # for any other account, make_note uses that account's default folder
    account_name = account_name or config.account
    if not folder_name and account_name == config.account:
        folder_name = config.folder
    editor = config.editor

    if file:
        note_text = file.read()
    elif url:
        try:
            # imported here so library and other commands don't pay for loading lxml
            from .readable import get_readable_html

            name, body = get_readable_html(url)
            note_text = f"{name}\n{body}"
        except Exception as e:
            raise click.ClickException(f"Could not download '{url}': {e}") from e
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
        raise click.ClickException("No note text.")

    note_text = note_text.strip()
    note_parts = note_text.partition("\n")
    name, body = note_parts[0], note_parts[2]

    if format_ == FORMAT_MARKDOWN:
        body = markdown_to_html(body)
    elif format_ != FORMAT_HTML:
        body = text_to_html(body)

    account = notes.account(account_name)
    new_note = account.make_note(name, body, folder_name)
    if show:
        new_note.show()


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
@click.option(
    "--json",
    "-j",
    "json_",
    is_flag=True,
    help="Output as JSON. Includes note metadata but not the body; "
    "use `notes cat --json` for the body.",
)
@click.argument("text", metavar="TEXT", required=False)
def list_notes(account_name, json_, text):
    """List notes, optionally filtering by account or text."""
    noteslist = get_notes_app().noteslist(
        accounts=list(account_name) if account_name else None,
        text=[text] if text else None,
    )
    if json_:
        records = noteslist.asdict(body=False)
        for record in records:
            record["creation_date"] = isoformat(record["creation_date"])
            record["modification_date"] = isoformat(record["modification_date"])
        click.echo(json.dumps(records, indent=4))
    else:
        print_notes_list(noteslist)


@click.command(name="cat")
@click.option("--plaintext", "-p", is_flag=True, help="Output note as plain text.")
@click.option("--markdown", "-m", is_flag=True, help="Output note as Markdown.")
@click.option("--html", "-H", is_flag=True, help="Output note as HTML.")
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
    """Print notes whose name contains NOTE_NAME to STDOUT"""
    if sum([plaintext, markdown, html]) > 1:
        raise click.UsageError(
            "Only one of --plaintext, --markdown, and --html can be specified."
        )
    notes = get_notes_app().notes(name=[name])
    if not notes:
        raise NotFoundError(f"No notes found with name containing '{name}'.")
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
        print_notes_as_json(notes, body_format="html" if output == "rich" else output)
    else:
        for note in notes:
            print_note(note, output=output)


@click.command(name="config")
def config():
    """Configure default settings for account, editor, etc."""
    import questionary

    notes = get_notes_app()
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
    notesapp = get_notes_app()
    if selected:
        for note in notesapp.selection:
            dump_note(note, no_body=no_body)
    else:
        for account in notesapp.accounts:
            noteslist = notesapp.noteslist(accounts=[account])
            dump_notes_list(noteslist, account, no_body=no_body)


def note_selection_options(func):
    """Decorator to add options for selecting a single note to a command"""
    options = [
        click.option(
            "--id",
            "note_id",
            metavar="ID",
            type=str,
            help="Select note by ID instead of by name (see `notes cat --json`).",
        ),
        click.option(
            "--contains",
            is_flag=True,
            help="Match notes whose name contains NOTE_NAME instead of matching the name exactly.",
        ),
        click.option(
            "--account",
            "-a",
            "account_name",
            metavar="ACCOUNT",
            type=str,
            help="Account to search in.",
        ),
    ]
    for option in reversed(options):
        func = option(func)
    return func


def resolve_note(
    notes_app: macnotesapp.NotesApp,
    note_name: str | None,
    note_id: str | None,
    account_name: str | None,
    contains: bool = False,
) -> macnotesapp.Note:
    """Return the single note selected by name or ID.

    By default NOTE_NAME must match the note's name exactly (case-insensitive).

    Raises:
        click.UsageError: if neither or both of note_name and note_id are given
        NotFoundError: if no note matches
        click.ClickException: if more than one note matches
    """
    accounts = [account_name] if account_name else None
    if note_id and note_name:
        raise click.UsageError("Specify NOTE_NAME or --id, not both.")
    if note_id:
        matches = notes_app.notes(id=[note_id], accounts=accounts)
        description = f"with ID '{note_id}'"
    elif note_name:
        matches = notes_app.notes(
            name=[note_name], accounts=accounts, exact_name=not contains
        )
        description = (
            f"with name containing '{note_name}'" if contains else f"'{note_name}'"
        )
    else:
        raise click.UsageError("Specify NOTE_NAME or --id.")

    if not matches:
        hint = "" if contains or note_id else " (use --contains for a partial match)"
        raise NotFoundError(f"Note {description} not found{hint}.")
    if len(matches) > 1:
        candidates = "\n".join(
            f"  {note.account}/{note.folder}: {note.name} "
            f"(modified {note.modification_date:%Y-%m-%d %H:%M}) --id {note.id}"
            for note in matches
        )
        raise click.ClickException(
            f"{len(matches)} notes match {description}; select one with --id:\n"
            f"{candidates}"
        )
    return matches[0]


@click.command(name="rename")
@click.argument("names", metavar="[OLD_NAME] NEW_NAME", nargs=-1, required=True)
@note_selection_options
def rename_note(names, note_id, contains, account_name):
    """Rename a note.

    OLD_NAME must match the note's name exactly (case-insensitive) unless --contains is given.
    If --id is given, only NEW_NAME is required.

    Example: notes rename "Old Title" "New Title"
    """
    expected = 1 if note_id else 2
    if len(names) != expected:
        usage = "--id ID NEW_NAME" if note_id else "OLD_NAME NEW_NAME"
        raise click.UsageError(f"Expected: notes rename {usage}")
    old_name = None if note_id else names[0]
    new_name = names[-1]
    notes_app = get_notes_app()
    note = resolve_note(notes_app, old_name, note_id, account_name, contains)
    old = note.name
    note.name = new_name
    click.echo(f"Renamed '{old}' -> '{new_name}'")


@click.command(name="delete")
@click.argument("note_name", metavar="NOTE_NAME", required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@note_selection_options
def delete_note(note_name, yes, note_id, contains, account_name):
    """Delete a note.

    NOTE_NAME must match the note's name exactly (case-insensitive) unless --contains is given.

    Example: notes delete "Old Note"
    """
    notes_app = get_notes_app()
    note = resolve_note(notes_app, note_name, note_id, account_name, contains)
    name = note.name
    if not yes:
        if not click.confirm(f"Delete '{name}'?"):
            click.echo("Aborted.")
            sys.exit(0)
    note.delete()
    click.echo(f"Deleted '{name}'")


@click.command(name="edit")
@click.argument("note_name", metavar="NOTE_NAME", required=False)
@click.option(
    "--body",
    "-b",
    help="Replace the body of the note (keeping its title) without opening the editor.",
)
@click.option(
    "--html",
    "-H",
    "use_html",
    is_flag=True,
    help="Treat --body as HTML, or edit the note's HTML in the editor.",
)
@click.option(
    "--markdown", "-m", "use_markdown", is_flag=True, help="Treat --body as Markdown."
)
@click.option(
    "--force",
    is_flag=True,
    help="Edit even if content such as attachments or formatting would be lost.",
)
@note_selection_options
def edit_note(
    note_name, body, use_html, use_markdown, force, note_id, contains, account_name
):
    """Edit an existing note's body.

    NOTE_NAME must match the note's name exactly (case-insensitive) unless --contains is given.

    Without --body, the note is opened in the default editor as Markdown
    (or as HTML with --html). Converting to Markdown and back loses
    tables, images, and styling, and writing the body loses attachments,
    so edit refuses to modify notes containing these unless --force is given.
    Checklists cannot be detected yet and will be converted to bulleted lists.

    Example: notes edit "My Note" --body "New content"
    """
    if use_html and use_markdown:
        raise click.UsageError("Only one of --html and --markdown can be specified.")
    notes_app = get_notes_app()
    note = resolve_note(notes_app, note_name, note_id, account_name, contains)
    original_name = note.name

    # check for content that would be lost by replacing the body
    lost = []
    if attachment_count := len(note.attachments):
        lost.append(f"{attachment_count} attachment(s)")
    if body is None and not use_html:
        lost.extend(markdown_lossy_features(note.body))
    if lost and not force:
        alternative = (
            "" if body is not None or use_html else "--html to edit the HTML, or "
        )
        raise click.ClickException(
            f"Editing '{original_name}' would lose content: {', '.join(lost)}. "
            f"Use {alternative}--force to edit anyway."
        )

    if body is not None:
        if use_markdown:
            body = markdown_to_html(body)
        elif not use_html:
            body = text_to_html(body)
        note.body = title_html(original_name) + body
        click.echo(f"Updated '{original_name}'")
        return

    current_body = note.body
    text = current_body if use_html else html_to_markdown(current_body)
    new_text = click.edit(
        text,
        editor=ConfigSettings().editor,
        extension=".html" if use_html else ".md",
    )
    if new_text is None:
        click.echo(f"No changes made to '{original_name}'")
        return
    note.body = new_text if use_html else markdown_to_html(new_text)
    click.echo(f"Updated '{original_name}'")


@click.command(name="move")
@click.argument("note_name", metavar="NOTE_NAME", required=False)
@click.option("--folder", "-f", required=True, help="Destination folder.")
@note_selection_options
def move_note(note_name, folder, note_id, contains, account_name):
    """Move a note to a different folder.

    NOTE_NAME must match the note's name exactly (case-insensitive) unless --contains is given.

    Example: notes move "My Note" --folder "Archive"
    """
    notes_app = get_notes_app()
    note = resolve_note(notes_app, note_name, note_id, account_name, contains)
    name = note.name
    old_folder = note.folder
    note.move(folder)
    click.echo(f"Moved '{name}' from '{old_folder}' to '{folder}'")


@click.command(name="mkdir")
@click.argument("folder_name", metavar="FOLDER_NAME")
@click.option(
    "--account",
    "-a",
    "account_name",
    metavar="ACCOUNT",
    type=str,
    help="Account to create folder in.",
)
def make_folder(folder_name, account_name):
    """Create a new folder.

    Example: notes mkdir "Archive"
    """
    notes_app = get_notes_app()
    account_name = account_name or notes_app.default_account
    account = notes_app.account(account_name)
    account.make_folder(folder_name)
    click.echo(f"Created folder '{folder_name}' in {account_name}")


@click.command(name="rmdir")
@click.argument("folder_name", metavar="FOLDER_NAME")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.option(
    "--account",
    "-a",
    "account_name",
    metavar="ACCOUNT",
    type=str,
    help="Account to delete folder from.",
)
def remove_folder(folder_name, yes, account_name):
    """Delete a folder.

    Example: notes rmdir "Old Folder"
    """
    notes_app = get_notes_app()
    account_name = account_name or notes_app.default_account
    account = notes_app.account(account_name)
    if folder_name not in account.folders:
        raise NotFoundError(f"Folder '{folder_name}' not found in {account_name}.")
    if not yes:
        if not click.confirm(f"Delete folder '{folder_name}' and all its notes?"):
            click.echo("Aborted.")
            sys.exit(0)
    account.delete_folder(folder_name)
    click.echo(f"Deleted folder '{folder_name}' from {account_name}")


# Click CLI object & context settings
class CLI_Obj:
    def __init__(self, debug=False, group=None):
        self.debug = debug
        self.group = group


CTX_SETTINGS = dict(help_option_names=["-h", "--help"])


class NotesGroup(click.Group):
    """Click group that reports errors as messages with an exit code instead of tracebacks"""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except (click.ClickException, click.exceptions.Exit, click.Abort):
            raise
        except NotesPermissionError as e:
            raise click.ClickException(str(e)) from e
        except Exception as e:
            if get_debug():
                raise
            message = str(e) or type(e).__name__
            raise click.ClickException(
                f"{message}\nRun `notes --debug ...` to see the full error."
            ) from e


@click.group(cls=NotesGroup, context_settings=CTX_SETTINGS)
@click.option(
    "--debug",
    required=False,
    is_flag=True,
    help="Show debug output and full tracebacks for errors.",
)
@click.version_option(__version__, "--version", "-v")
@click.pass_context
def cli_main(ctx, debug):
    """notes: work with Apple Notes on the command line.

    Exit codes: 0 success, 1 error, 2 usage error, 3 note or folder not found.
    """
    set_debug(debug)
    ctx.obj = CLI_Obj(debug=debug, group=cli_main)


# add the commands to the main group
for command in [
    accounts,
    add_note,
    cat_notes,
    config,
    list_notes,
    dump,
    help,
    rename_note,
    delete_note,
    edit_note,
    move_note,
    make_folder,
    remove_folder,
]:
    cli_main.add_command(command)


def get_account_data() -> dict:
    """Get dict of account data for Notes accounts"""
    notes = get_notes_app()
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
    click.echo(format_str.format("Folder", "Name", "Body"))
    for note in zip(folders, names, body, strict=True):
        folder, name, body = note
        folder = folder or "---"
        name = name or "---"
        body = body or "---"
        name = (
            f"{name[: name_len - padding]}.."
            if len(name) > (name_len - padding)
            else name
        )
        body = body.replace("\n", " ")
        body = (
            f"{body[: body_len - padding]}.."
            if len(body) > (body_len - padding)
            else body
        )
        click.echo(format_str.format(folder, name, body))


def print_note(note: macnotesapp.Note, output: str):
    """Print a note to STDOUT

    Args:
        note: Note to print
        output: Output format (plaintext, markdown, html, rich)
    """

    # click.echo for raw output: Console.print would interpret [text] as Rich markup
    if output == "plaintext":
        click.echo(note.plaintext)
    elif output == "rich":
        Console().print(Markdown(html_to_markdown(note.body)))
    elif output == "markdown":
        click.echo(html_to_markdown(note.body))
    elif output == "html":
        click.echo(note.body)


def print_notes_as_json(notes: Iterable[macnotesapp.Note], body_format: str = "html"):
    """Print notes as JSON to STDOUT

    Args:
        notes: Notes to print
        body_format: format of note body: "html", "plaintext", or "markdown"
    """

    json_list = []
    for note in notes:
        json_data = note.asdict()
        if body_format == "plaintext":
            json_data["body"] = json_data["plaintext"]
        elif body_format == "markdown":
            json_data["body"] = html_to_markdown(json_data["body"])
        del json_data["plaintext"]
        json_data["creation_date"] = isoformat(json_data["creation_date"])
        json_data["modification_date"] = isoformat(json_data["modification_date"])
        json_list.append(json_data)
    click.echo(json.dumps(json_list, indent=4))


def dump_note(note: macnotesapp.Note, no_body: bool = False):
    """Dump note data to STDOUT for debugging purposes"""
    click.echo(f"{note.id=}")
    click.echo(f"{note.name=}")
    click.echo(f"{note.account=}")
    click.echo(f"{note.folder=}")
    click.echo(f"{note.creation_date=}")
    click.echo(f"{note.modification_date=}")
    click.echo(f"{note.password_protected=}")
    if not no_body:
        click.echo(f"{note.body=}")
        click.echo(f"{note.plaintext=}")


def dump_notes_list(
    noteslist: macnotesapp.NotesList, account: str, no_body: bool = False
):
    """Dump NotesList data to STDOUT for debugging purposes"""
    notesdicts = noteslist.asdict()
    for notesdict in notesdicts:
        click.echo(f"note.id={notesdict['id']}")
        click.echo(f"note.name={notesdict['name']}")
        click.echo(f"note.folder={notesdict['folder']}")
        click.echo(f"note.account={account}")
        click.echo(f"note.creation_date={notesdict['creation_date']}")
        click.echo(f"note.modification_date={notesdict['modification_date']}")
        click.echo(f"note.password_protected={notesdict['password_protected']}")
        if not no_body:
            click.echo(f"note.body={notesdict['body']}")
            click.echo(f"note.plaintext={notesdict['plaintext']}")
