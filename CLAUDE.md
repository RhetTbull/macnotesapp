# CLAUDE.md

This file guides Claude Code (claude.ai/code) when working in this repository.

## Project overview

`macnotesapp` is a Python library and CLI (`notes`) for automating Apple Notes.app on macOS. It runs only on macOS: it reads the Notes database with apple-notes-parser when it can, and drives Notes.app through ScriptingBridge (PyObjC) and AppleScript (`py-applescript`). Supported Python is 3.11–3.14.

## Commands

Dependencies are managed with [uv](https://docs.astral.sh/uv/). Run everything through `uv run`.

```bash
uv sync                          # create .venv and install deps (including dev)
uv run notes --help              # run the CLI from source
uv run pytest                    # unit tests only: no Notes.app access, safe to run anytime
uv run pytest --integration      # also run integration tests against Notes.app (temporary folders only)
uv run pytest --manual -s tests/manual   # interactive tests; prompt for input and change real notes
uv run ruff check && uv run ruff format   # lint and format (CI checks both)
uv run cog -r README.md          # regenerate the cog-generated sections of README.md
uv run mkdocs build              # build docs into site/
uv run bump2version <major|minor|patch> --verbose   # bump version
./build.sh                       # full release build (cog, docs, wheel, pyinstaller binary, homebrew sha)
```

## Testing caveats

Tests are split into three tiers (see `tests/conftest.py`):

- `tests/unit/`: uses fakes from `tests/unit/fakes.py` and never talks to Notes.app. This is all that runs by default and in CI. Add a unit test for every change that can be tested this way.
- `tests/integration/`: automated tests against the user's **real Notes.app**, enabled with `--integration`. They only create, change, and delete notes inside temporary `macnotesapp-test-*` folders in the default account, which are deleted afterwards (their notes go to Recently Deleted). Ask the user before running them.
- `tests/manual/`: enabled with `--manual` and must be run with `-s`. `test_interactive.py` prompts for input and changes notes the user selects. `test_readme.py` runs the README's Python blocks with `mktestdocs`, which create notes in the default folder. Don't run these without the user's go-ahead.

Beyond the fakes, no mocks exist for Notes.app. Read-only checks against Notes.app are fine, but print counts or booleans, not note contents.

## Architecture

### Reading the Notes database

`macnotesapp/database.py` (`NotesDatabase`) reads `NoteStore.sqlite` read-only through apple-notes-parser and returns `NoteRecord`s. `NotesApp(backend=...)` picks the read path: `"auto"` (default) uses the database when it opens and falls back to ScriptingBridge, `"database"` requires it, and `"scriptingbridge"` never uses it. The CLI's `--backend` option sets it.

- Accounts are matched by ID (`x-coredata://<Z_UUID>/ICAccount/p<Z_PK>`). Only accounts in the database (iCloud, On My Mac) use it; IMAP accounts (`.../IMAPNote/...` IDs) always use ScriptingBridge.
- `Account._noteslist()` returns a `DatabaseNotes` (records plus the account's SB notes, for bodies) instead of an SBElementArray. `Note` objects built from records use the record's values until the note is changed (`Note._changed()`).
- The body (HTML) isn't in the database and is always fetched from Notes.app.
- Never write to the database. It's opened with `mode=ro`, or `immutable=1` only when there's no `-shm` file and the `-wal` file is empty; otherwise SQLite would create files in Notes' container or return stale data.
- The database reloads when `PRAGMA data_version` changes.
- Notes.app saves changes to the database late, sometimes after 20+ s, and sometimes not at all (#86). Every write to a note goes through `Note._changing(kind)`, which records the database column that change updates (`CHANGE_COLUMNS`) with `notify_write()`. Until that column changes, `unsaved_note_ids()` includes the note, and `Account._noteslist()` reads it from Notes.app (`_record_from_notes_app()`) instead of the database. Folder changes make the next read wait briefly (`wait_for_writes()`).
- The CLI saves unsaved changes to `$XDG_STATE_HOME/macnotesapp/unsaved_changes.json` after each command and loads them in `get_notes_app()`, so the next command sees them. Tests redirect this file.
- Filtering must match ScriptingBridge: `contains[cd]` ignores case and diacritics; exact names (`==[c]`) ignore case only. Locked notes have empty text and no tags.
- Tags, `folder_path`, and `content_features()` (formatting and objects that edits would lose) exist only for notes in the database.
- `tests/unit/test_database.py` uses fixture databases in `tests/unit/data` from apple-notes-parser's tests.

### Two automation backends

`macnotesapp/notesapp.py` holds the public API: `NotesApp`, `Account`, `Folder`, `Note`, `NotesList`, and `Attachment`. It mixes two ways of talking to Notes.app:

1. **ScriptingBridge** (`ScriptingBridge.SBApplication` for bundle id `com.apple.Notes`): the fast path for reads. Each wrapper class holds an SB object (`self._note`, `self._account`, and so on). Strings returned from SB are PyObjC unicode objects, so wrap them in `str()` before returning them.
2. **AppleScript handlers** run through `script_loader.run_script(handler_name, *args)`. This is the fallback when SB returns bad data (for example, an object id of `0`) and the main path for writes such as setting the name or body, delete, move, adding attachments, and creating or deleting folders. `Note._run_script` and `Account._run_script` prepend the account name, and for notes the note id, to the arguments.

`NotesList` wraps SB element arrays and fetches properties in bulk. It is much faster than iterating `Note` objects, so prefer it for operations over many notes.

### AppleScript source

`macnotesapp/macnotesapp.applescript` holds every AppleScript handler. `script_loader.py` reads it as UTF-8 with `importlib.resources`, compiles it on the first `run_script()` call, and caches the result. Keep the file UTF-8: the `«class seld»` guillemets must survive. `tests/unit/test_script_loader.py` checks that the file compiles and that every handler called from Python is defined. Handler names follow the pattern `<object><Action>`, for example `noteGetBody(accountName, noteID)`, `folderCreate(accountName, folderName)`, or `notesGetAccounts()`. The PyInstaller spec bundles the file.

### CLI (`macnotesapp/cli/`)

- `cli.py` defines the Click group `cli_main` (entry point `notes = macnotesapp.__main__:cli_main`, class `NotesGroup`) and the subcommands `accounts`, `add`, `cat`, `config`, `list`, `dump`, `help`, `rename`, `delete`, `edit`, `move`, `mkdir`, and `rmdir`. Each command is a standalone `@click.command` registered in the list near `cli_main`. A new command must be added to that list.
- Commands get a `NotesApp` from `get_notes_app()`, which first checks the Automation permission (ScriptingBridge fails silently without it). Report errors by raising `click.UsageError` (exit 2), `NotFoundError` (exit 3), or `click.ClickException` (exit 1), not with `sys.exit`. `NotesGroup` turns any other exception into a one-line error, or a traceback with `--debug`.
- Commands that act on one note use `@note_selection_options` and `resolve_note()`: exact (case-insensitive) name match by default, `--contains`, `--id`, and refusal when more than one note matches.
- Print raw note content with `click.echo`, not Rich's `Console.print`, which treats `[text]` as markup.
- `cli_config.py` holds `ConfigSettings`, a TOML config at `$XDG_CONFIG_HOME/macnotesapp/macnotesapp.toml` (default account, editor, and body format).
- `cli_help.py` and `click_rich_echo.py` provide Rich-formatted help (`RichHelpCommand`) and output. Help text can contain Rich markup. `docs/strip_rich_markup.py` is an mkdocs hook that strips that markup for the docs site.
- `readable.py` handles `notes add --url`, using readability-lxml to extract article HTML.
- Bodies are HTML inside Notes. `macnotesapp/formatting.py` converts plain text (escaped), Markdown (`markdown2`), and HTML (`markdownify`). The note title is the first line of the body; build it with `notesapp.title_html()`.

### Repo-root `cli.py` and `macnotesapp.spec`

`cli.py` at the repo root is a thin wrapper used only by PyInstaller (`macnotesapp.spec`) to build the standalone `dist/notes` binary for the Homebrew formula (`HomebrewFormula/macnotesapp.rb`). It is not the installed entry point.

## Conventions and housekeeping

- **README.md is partly generated.** Blocks between `<!-- [[[cog` and `<!-- [[[end]]] -->` come from CLI `--help` output and `examples/example.py`. Don't hand-edit them. After changing CLI help or the example, run `uv run cog -r README.md`.
- **Versions live in three files** that `bump2version` keeps in sync (`.bumpversion.cfg`): `macnotesapp/_version.py`, `pyproject.toml`, and `HomebrewFormula/macnotesapp.rb`. Don't bump versions by hand.
- Lint and format with ruff (config in `pyproject.toml`). CI (`.github/workflows/ci.yml`) runs ruff, `cog --check`, unit tests on Python 3.11–3.14, and a package and docs build on macOS.
- Keep imports of heavy optional dependencies (requests, readability-lxml, validators, questionary, markdown libraries) inside the functions that use them, so importing the library or running unrelated commands stays fast.
- Exceptions live in `macnotesapp/errors.py` (`MacNotesAppError` base). `run_script` raises `NotesPermissionError` when Automation permission is denied.
- Logging goes through `macnotesapp.logging.logger`. Use `set_debug(True)` to enable debug output; the CLI's `--debug` flag does this.
- Known Notes.app limitations: locked password-protected notes can't be read, tags are stripped from bodies (but readable from the database), notes can only be created in or moved to top-level folders, and attachment handling is partial. See the README's "Known Issues". Notes.app's AppleScript dictionary is buggy on some macOS versions, which explains several workarounds in the script.
