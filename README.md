# MacNotesApp
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-3-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

Work with Apple MacOS Notes.app from the command line. Also includes python interface for scripting Notes.app from your own python code.

## Installation

There are two ways to install the command line tool: `pipx` or `homebrew`.

### Install with [pipx](https://pypa.github.io/pipx/)

If you use `pipx`, you will not need to create a python virtual environment as `pipx` takes care of this. The easiest way to do this on a Mac is to use [homebrew](https://brew.sh/):

* Open `Terminal` (search for `Terminal` in Spotlight or look in `Applications/Utilities`)
* Install `homebrew` according to instructions at [https://brew.sh/](https://brew.sh/)
* Type the following into Terminal: `brew install pipx`
* Then type this: `pipx install macnotesapp`
* `pipx` will install the `macnotesapp` command line interface (CLI) as an executable named `notes`
* Now you should be able to run `notes` by typing: `notes`

Once you've installed macnotesapp with pipx, to upgrade to the latest version:

    pipx upgrade macnotesapp

**Note**: Currently tested on MacOS 10.15.7/Catalina and 13.1/Ventura.

### Install with [homebrew](brew.sh)

* Install `homebrew` according to instructions at [https://brew.sh/](https://brew.sh/)

Once you have installed `homebrew`, you can install the CLI in the terminal with:

    brew tap RhetTbull/macnotesapp https://github.com/RhetTbull/macnotesapp
    brew update
    brew install macnotesapp

* Now you should be able to run `notes` by typing: `notes`

## Documentation

Full documentation available at [https://RhetTbull.github.io/macnotesapp/](https://RhetTbull.github.io/macnotesapp/)

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

Options:
  -v, --version  Show the version and exit.
  -h, --help     Show this message and exit.

Commands:
  accounts  Print information about Notes accounts.
  add       Add new note.
  cat       Print one or more notes to STDOUT
  config    Configure default settings for account, editor, etc.
  dump      Dump all notes or selection of notes for debugging
  help      Print help; for help on commands: help <command>.
  list      List notes, optionally filtering by account or text.

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

  Body of note must be plain text unless --html/-h or --markdown/-m
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
  -h, --html             Use HTML for body of note.
  -m, --markdown         Use Markdown for body of note.
  -p, --plaintext        Use plaintext for body of note (default unless changed
                         in `notes config`).
  -e, --edit             Edit note text before adding in default editor.
  -a, --account ACCOUNT  Add note to account ACCOUNT.
  -f, --folder FOLDER    Add note to folder FOLDER.
  --help                 Show this message and exit.

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

```
<!-- [[[end]]] -->

## Known Issues and Limitations

* Password protected notes are not supported; unlocked password-protected notes can be accessed but locked notes cannot
* Notes containing tags (#tagname) can be read but the tags will be stripped from the body of the note
* Tags cannot be added to notes and will show up as plaintext if added manually with macnotesapp
* Currently, only notes in top-level folders are accessible to `macnotesapp` (#4)
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
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!
