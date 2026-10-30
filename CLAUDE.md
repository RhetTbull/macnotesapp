# CLAUDE.md

This file guides Claude Code (claude.ai/code) when working in this repository.

## Project overview

`macnotesapp` is a Python library and CLI (`notes`) for automating Apple Notes.app on macOS. It runs only on macOS: it drives Notes.app through ScriptingBridge (PyObjC) and AppleScript (`py-applescript`). Supported Python is 3.10–3.13.

## Commands

Dependencies are managed with [uv](https://docs.astral.sh/uv/). Run everything through `uv run`.

```bash
uv sync                          # create .venv and install deps (including dev)
uv run notes --help              # run the CLI from source
uv run pytest -v -s tests/       # run tests (-s is REQUIRED: tests are interactive)
uv run pytest -v -s tests/test_applescript_interface.py::test_notes_len   # run a single test
uv run cog -r README.md          # regenerate the cog-generated sections of README.md
uv run mkdocs build              # build docs into site/
uv run bump2version <major|minor|patch> --verbose   # bump version
./build.sh                       # full release build (cog, docs, wheel, pyinstaller binary, homebrew sha)
```

## Testing caveats

- Tests run against the user's **real Notes.app data**. Many tests prompt `y/n` on stdin to confirm what they print, and some create, modify, or delete notes and folders. Don't run the test suite without the user's go-ahead, and never run it non-interactively expecting it to pass.
- `tests/test_docs.py` uses `mktestdocs` to execute the Python code blocks in `README.md`. Those blocks also touch Notes.app and create notes.
- No mocks exist for Notes.app. To verify a change, run the relevant CLI command or library call against Notes.app, with the user's consent if it writes data.

## Architecture

### Two automation backends

`macnotesapp/notesapp.py` holds the public API: `NotesApp`, `Account`, `Folder`, `Note`, `NotesList`, and `Attachment`. It mixes two ways of talking to Notes.app:

1. **ScriptingBridge** (`ScriptingBridge.SBApplication` for bundle id `com.apple.Notes`): the fast path for reads. Each wrapper class holds an SB object (`self._note`, `self._account`, and so on). Strings returned from SB are PyObjC unicode objects, so wrap them in `str()` before returning them.
2. **AppleScript handlers** run through `script_loader.run_script(handler_name, *args)`. This is the fallback when SB returns bad data (for example, an object id of `0`) and the main path for writes such as setting the name or body, delete, move, adding attachments, and creating or deleting folders. `Note._run_script` and `Account._run_script` prepend the account name, and for notes the note id, to the arguments.

`NotesList` wraps SB element arrays and fetches properties in bulk. It is much faster than iterating `Note` objects, so prefer it for operations over many notes.

### AppleScript source lives in two places

- `macnotesapp/macnotesapp.applescript` is the reference copy. It is **not UTF-8**: the `«class seld»` guillemets are stored in a legacy Mac encoding.
- `macnotesapp/macnotesapp_applescript.py` holds the same script pasted into the `NOTES_APPLESCRIPT` string. **This copy is the one that runs.**

When you add or change an AppleScript handler, edit both files and keep them in sync. Handler names follow the pattern `<object><Action>`, for example `noteGetBody(accountName, noteID)`, `folderCreate(accountName, folderName)`, or `notesGetAccounts()`.

### CLI (`macnotesapp/cli/`)

- `cli.py` defines the Click group `cli_main` (entry point `notes = macnotesapp.__main__:cli_main`) and the subcommands `accounts`, `add`, `cat`, `config`, `list`, `dump`, `help`, `rename`, `delete`, `edit`, `move`, `mkdir`, and `rmdir`. Each command is a standalone `@click.command` registered in the list near `cli_main`. A new command must be added to that list.
- `cli_config.py` holds `ConfigSettings`, a TOML config at `$XDG_CONFIG_HOME/macnotesapp/macnotesapp.toml` (default account, editor, and body format).
- `cli_help.py` and `click_rich_echo.py` provide Rich-formatted help (`RichHelpCommand`) and output. Help text can contain Rich markup. `docs/strip_rich_markup.py` is an mkdocs hook that strips that markup for the docs site.
- `readable.py` handles `notes add --url`, using readability-lxml to extract article HTML.
- Bodies are HTML inside Notes. The CLI converts Markdown to HTML with `markdown2` (`MARKDOWN_EXTRAS`) and HTML to Markdown with `markdownify`.

### Repo-root `cli.py` and `macnotesapp.spec`

`cli.py` at the repo root is a thin wrapper used only by PyInstaller (`macnotesapp.spec`) to build the standalone `dist/notes` binary for the Homebrew formula (`HomebrewFormula/macnotesapp.rb`). It is not the installed entry point.

## Conventions and housekeeping

- **README.md is partly generated.** Blocks between `<!-- [[[cog` and `<!-- [[[end]]] -->` come from CLI `--help` output and `examples/example.py`. Don't hand-edit them. After changing CLI help or the example, run `uv run cog -r README.md`.
- **Versions live in three files** that `bump2version` keeps in sync (`.bumpversion.cfg`): `macnotesapp/_version.py`, `pyproject.toml`, and `HomebrewFormula/macnotesapp.rb`. Don't bump versions by hand.
- Imports follow isort's `black` profile (`.isort.cfg`). Format code in black style.
- Logging goes through `macnotesapp.logging.logger`. Use `set_debug(True)` to enable debug output. The hidden CLI `--debug` flag is not currently wired to `set_debug()`.
- Known Notes.app limitations: locked password-protected notes are unsupported, tags are stripped, only top-level folders are accessible, and attachment handling is partial. See the README's "Known Issues". Notes.app's AppleScript dictionary is buggy on some macOS versions, which explains several workarounds in the script.
