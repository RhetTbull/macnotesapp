# MacNotesApp
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-5-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

Work with Apple MacOS Notes.app from the command line. Also includes python interface for scripting Notes.app from your own python code.

## Installation
## Installation

The recommended way to install `macnotesapp` is via the [uv](https://github.com/astral-sh/uv) python package manager tool.

### Installation using `uv`

* Open `Terminal` (search for `Terminal` in Spotlight or look in `Applications/Utilities`)
* Install `uv` by running the following command in Terminal:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

If you previously installed `uv`, upgrade to the latest version:

```bash
uv self update
```

* Type the following into Terminal:

```bash
uv tool install --python 3.13 macnotesapp
```

* Now you should be able to run `macnotesapp` by typing: `macnotesapp`

Once you've installed macnotesapp with `uv`, to upgrade to the latest version:

```bash
uv tool upgrade macnotesapp
```

If you want to try `macnotesapp` without installing it, you can run `uv tool run --python 3.13 macnotesapp` or `uvx --python 3.13 macnotesapp`.

Note: If installing on an older version of macOS and you encounter issues installing with uv, try installing python 3.13 from [python.org](https://www.python.org/downloads/) then running uv to install macnotesapp.

**Note**: Currently tested on MacOS 10.15.7/Catalina and 13.1/Ventura.

### Install with [homebrew](brew.sh)

* Install `homebrew` according to instructions at [https://brew.sh/](https://brew.sh/)

Once you have installed `homebrew`, you can install the CLI in the terminal with:

    brew tap RhetTbull/macnotesapp https://github.com/RhetTbull/macnotesapp
    brew update
    brew install macnotesapp

* Now you should be able to run `notes` by typing: `notes`

**Note**: This only works for Apple Silicon (M1, etc.) Macs. If you are using an Intel Mac, use the uv instructions above.

## Documentation

Full documentation available at [https://RhetTbull.github.io/macnotesapp/](https://RhetTbull.github.io/macnotesapp/)

## Reading notes from the Notes database

When it can, macnotesapp reads notes directly from the Notes database (`NoteStore.sqlite`) using [apple-notes-parser](https://github.com/RhetTbull/apple-notes-parser) instead of asking Notes.app for each one. This is much faster (listing a couple of thousand notes takes seconds instead of a minute) and adds tags, the full folder path of notes in subfolders, and detection of content that `notes edit` would lose, such as checklists.

Reading the database requires Full Disk Access for your terminal app (System Settings > Privacy & Security > Full Disk Access), or allowing access to data from other apps when macOS asks. Without it, macnotesapp reads notes through Notes.app as before. Notes in IMAP accounts such as Google aren't stored in the database and are always read through Notes.app. Creating and changing notes always goes through Notes.app.

Notes.app writes changes to its database on its own schedule, sometimes 20 seconds or more after they are made (#86). macnotesapp keeps track of the changes it makes and reads those notes from Notes.app until they are saved, but changes made in Notes.app itself may take a moment to appear.

To choose explicitly, use `notes --backend scriptingbridge ...` (never read the database) or `notes --backend database ...` (fail if it can't be read), or `NotesApp(backend=...)` in Python.

## Command Line Usage

<!-- [[[cog
import cog
from macnotesapp.cli import cli_main
from click.testing import CliRunner
runner = CliRunner()
result = runner.invoke(cli_main, ["--help"])
help = result.output.replace("Usage: cli-main", "Usage: notes")
cog.out(
    "```\n{}\n```".format(help)
)
]]] -->
```
Usage: notes [OPTIONS] COMMAND [ARGS]...

  notes: work with Apple Notes on the command line.

  Exit codes: 0 success, 1 error, 2 usage error, 3 note or folder not found.

Options:
  --debug                         Show debug output and full tracebacks for
                                  errors.
  --backend [auto|database|scriptingbridge]
                                  Where to read notes from: the Notes database
                                  (fast; needs Full Disk Access) or Notes.app
                                  via ScriptingBridge. 'auto' uses the database
                                  when it is readable. Changes always go through
                                  Notes.app.  [default: auto]
  -v, --version                   Show the version and exit.
  -h, --help                      Show this message and exit.

Commands:
  accounts  Print information about Notes accounts.
  add       Add new note.
  cat       Print notes whose name contains NOTE_NAME to STDOUT
  config    Configure default settings for account, editor, etc.
  delete    Delete a note.
  dump      Dump all notes or selection of notes for debugging
  edit      Edit an existing note's body.
  help      Print help; for help on commands: help <command>.
  list      List notes, optionally filtering by account, tag, or text.
  mkdir     Create a new folder.
  move      Move a note to a different folder.
  rename    Rename a note.
  rmdir     Delete a folder.

```
<!-- [[[end]]] -->

Use `notes help COMMAND` to get help on a specific command. For example, `notes help add`:

<!-- [[[cog
import cog
from macnotesapp.cli import cli_main
from click.testing import CliRunner
runner = CliRunner()
result = runner.invoke(cli_main, ["help", "add", "--no-markup"])
help = result.output.replace("Usage: cli-main", "Usage: notes")
cog.out(
    "```\n{}\n```".format(help)
)
]]] -->
```
Usage: notes add [OPTIONS] NOTE

  Add new note.

  There are multiple ways to add a new note:

  Add a new note from standard input (STDIN):

  notes add

  cat file.txt | notes add

  notes add < file.txt

  Add a new note by passing string on command line:

  notes add NOTE

  Add a new note by opening default editor (defined in $EDITOR or via `notes
  config`):

  notes add --edit

  notes add -e

  Add a new note from URL (downloads URL, creates a cleaned readable version
  to store in new Note):

  notes add --url URL

  notes add -u URL

  If NOTE is a single line, adds new note with name NOTE and no body. If NOTE is
  more than one line, adds new note where name is first line of NOTE and body is
  remainder.

  Body of note must be plain text unless --html/-H or --markdown/-m
  flag is set in which case body should be HTML or Markdown, respectively. If
  --edit/-e flag is set, note will be opened in default editor before
  being added. If --show/-s flag is set, note will be shown in Notes.app
  after being added.

  Account and top level folder may be specified with --account/-a and
  --folder/-f, respectively. If not provided, default account and folder
  are used.

Options:
  -s, --show             Show note in Notes after adding.
  -F, --file FILENAME
  -u, --url URL
  -H, --html             Use HTML for body of note.
  -m, --markdown         Use Markdown for body of note.
  -p, --plaintext        Use plaintext for body of note (default unless changed
                         in `notes config`).
  -e, --edit             Edit note text before adding in default editor.
  -a, --account ACCOUNT  Add note to account ACCOUNT.
  -f, --folder FOLDER    Add note to folder FOLDER.
  -h, --help             Show this message and exit.

```
<!-- [[[end]]] -->

## Python Usage

<!-- [[[cog
import cog
with open("examples/example.py") as f:
    example = f.read()
cog.out(
    "```python\n{}\n```".format(example)
)
]]] -->
```python
"""Example code for working with macnotesapp"""

from macnotesapp import NotesApp

# NotesApp() provides interface to Notes.app
notesapp = NotesApp()

# Get list of notes (Note objects for each note)
notes = notesapp.notes()
note = notes[0]
print(
    note.id,
    note.account,
    note.folder,
    note.name,
    note.body,
    note.plaintext,
    note.password_protected,
)

print(note.asdict())

# Get list of notes for one or more specific accounts
notes = notesapp.notes(accounts=["iCloud"])

# Create a new note in default folder of default account
new_note = notesapp.make_note(
    name="New Note", body="This is a new note created with #macnotesapp"
)

# Create a new note in a specific folder of a specific account
account = notesapp.account("iCloud")
account.make_note(
    "My New Note", "This is a new note created with #macnotesapp", folder="Notes"
)

# If working with many notes, it is far more efficient to use the NotesList object
# Find all notes with "#macnotesapp" in the body
noteslist = notesapp.noteslist(body=["#macnotesapp"])

print(f"There are {len(noteslist)} notes with #macnotesapp in the body")

# List of names of notes in noteslist
note_names = noteslist.name
print(note_names)

# When the Notes database is readable, notes also have tags and a full folder path
if notesapp.database:
    for note in notesapp.notes(tag=["recipes"]):
        print(note.folder_path, note.name, note.tags)

```
<!-- [[[end]]] -->

## See Also

* [apple-notes-parser](https://github.com/RhetTbull/apple-notes-parser): Reads data directly from the Apple Notes database. Read-only but is faster than using the AppleScript API. Supports tags and folders.
* [mcp-apple-notes-py](https://github.com/mcolyer/mcp-apple-notes-py): MCP server that uses macnotesapp and apple-notes-parser; provides LLMs access to your notes.

## Known Issues and Limitations

* Locked password-protected notes can be listed but not read; their text is empty
* Tags can be read (`note.tags`, `notes list --tag`) only when the Notes database is readable, and are stripped from the note's body
* Tags cannot be added to notes and will show up as plaintext if added manually with macnotesapp
* Notes in subfolders can be read (`note.folder_path` gives the full path when the database is readable), but notes can only be created in or moved to top-level folders (#4)
* Attachments are not currently handled and will be ignored (#15)
* The title style is not correctly set (#13)

## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/chadmando"><img src="https://avatars.githubusercontent.com/u/20407042?v=4?s=100" width="100px;" alt="chadmando"/><br /><sub><b>chadmando</b></sub></a><br /><a href="#userTesting-chadmando" title="User Testing">📓</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/JonathanDoughty"><img src="https://avatars.githubusercontent.com/u/1918593?v=4?s=100" width="100px;" alt="JonathanDoughty"/><br /><sub><b>JonathanDoughty</b></sub></a><br /><a href="https://github.com/RhetTbull/macnotesapp/issues?q=author%3AJonathanDoughty" title="Bug reports">🐛</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://skife.org/"><img src="https://avatars.githubusercontent.com/u/1291?v=4?s=100" width="100px;" alt="Brian McCallister"/><br /><sub><b>Brian McCallister</b></sub></a><br /><a href="https://github.com/RhetTbull/macnotesapp/commits?author=brianm" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://twitter.com/furman"><img src="https://avatars.githubusercontent.com/u/468007?v=4?s=100" width="100px;" alt="Andrew Furman"/><br /><sub><b>Andrew Furman</b></sub></a><br /><a href="https://github.com/RhetTbull/macnotesapp/commits?author=andrewfurman" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/bwagner"><img src="https://avatars.githubusercontent.com/u/447049?v=4?s=100" width="100px;" alt="Bernhard Wagner"/><br /><sub><b>Bernhard Wagner</b></sub></a><br /><a href="https://github.com/RhetTbull/macnotesapp/issues?q=author%3Abwagner" title="Bug reports">🐛</a> <a href="https://github.com/RhetTbull/macnotesapp/commits?author=bwagner" title="Tests">⚠️</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!
