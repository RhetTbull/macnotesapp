# MacNotesApp

Work with Apple MacOS Notes.app from the command line. Also includes python interface for scripting Notes.app from your own python code. Interactive browsing of notes in a TUI (Terminal User Interface? Textual User Interface?) coming soon!

## Installation

If you just want to use the command line tool, the easiest option is to install via [pipx](https://pypa.github.io/pipx/).

If you use `pipx`, you will not need to create a python virtual environment as `pipx` takes care of this. The easiest way to do this on a Mac is to use [homebrew](https://brew.sh/):

* Open `Terminal` (search for `Terminal` in Spotlight or look in `Applications/Utilities`)
* Install `homebrew` according to instructions at [https://brew.sh/](https://brew.sh/)
* Type the following into Terminal: `brew install pipx`
* Then type this: `pipx install macnotesapp`
* `pipx` will install the `macnotesapp` command line interface (CLI) as an executable named `notes`
* Now you should be able to run `notes` by typing: `notes`

Once you've installed macnotesapp with pipx, to upgrade to the latest version:

    pipx upgrade macnotesapp

**Note**: Currently tested on MacOS 10.15.7/Catalina; should run on newer versions of MacOS but I have not yet tested this.

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
  config    Configure default settings for account, editor, etc.
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

## Known Issues

* Currently, only notes in top-level folders are accessible to `macnotesapp`.
* Only tested on MacOS 10.15.7.
