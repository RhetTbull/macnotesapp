# macnotesapp Roadmap

The goal is to make `macnotesapp` a robust Python package and CLI for working with Apple Notes. This roadmap groups the open issues into phases. Each phase is meant to ship as one or more releases. Phases 0 and 1 make the existing tool safe and testable. Phase 2 replaces the slow read path. Later phases build features on top of that.

## Architecture direction

- **Reads** move to [apple-notes-parser](https://github.com/RhetTbull/apple-notes-parser) (#70), which reads `NoteStore.sqlite` directly. It sits behind a backend interface on `NotesApp`. The default `"auto"` mode uses the parser when the database is readable (Full Disk Access or App Data permission) and falls back to ScriptingBridge when it isn't.
- **Writes** stay on AppleScript and ScriptingBridge, which go through Notes.app and therefore through its CRDT merge and CloudKit sync logic.
- **Ids line up across both paths.** AppleScript note ids have the form `x-coredata://<store UUID>/ICNote/p<Z_PK>`. The store UUID is in `Z_METADATA.Z_UUID` and `Z_PK` is the row's primary key, so parser results map deterministically onto the ids that the write path uses.

### Private frameworks

`NotesShared.framework` loads through PyObjC on macOS 27 and exposes `ICNoteContext`, `ICNote`, `ICAttachment`, `ICHashtag`, and `ICTTMergeableString`. `NotesHTML.framework` and `NotesEditor.framework` are also present.

**Don't use them for writes.**

- Writing to the Core Data store from an unentitled process bypasses Notes.app's merge and sync logic and risks corrupting notes or causing sync conflicts.
- The group container holds a `SharingExtensionWriteLock` file, which shows that Apple coordinates out-of-process writers explicitly.
- The API has no headers and changes between releases.

For reads, the parser gets most of the performance benefit and is less fragile. #32 stays open as a time-boxed spike with one question: can `NotesHTML`/`NotesShared` render a note to faithful HTML, including checklists, tables, and attachments? That would be the most valuable private-framework result, because it would make export (#23) faithful. Stop the spike if it needs entitlements we can't get or crashes across OS versions.

## Phase 0: Correctness and safety

Small fixes, most of which can be unit-tested without Notes.app. #74 should land before any new write commands are added.

| Issue | Summary |
|---|---|
| #72 | Account filtering broken (`notes list -a`, `--account`, `dump`); predicate args mutate the caller's lists |
| #73 | `-h` means both `--help` and `--html` |
| #74 | Write commands act on the first substring match. Add exact match, `--id`, and refuse when the match is ambiguous |
| #75 | `edit` loses content in the Markdown round trip. First step: refuse to replace rich content without `--force` |
| #76 | Titles and plain-text bodies aren't HTML-escaped (closes #38) |
| #77 | `Note.folder` crash, `NotesList` field misalignment, `Note.id` returning `0` |
| #78 | `Note.account` costs an AppleScript round trip on every note operation |

## Phase 1: Foundations

| Issue | Summary |
|---|---|
| #82 | Non-interactive test tiers in a sandbox folder, plus GitHub Actions CI (absorbs #11 and #2) |
| #80 | Single-source the AppleScript as a UTF-8 file, compile lazily, remove dead handlers |
| #81 | Python 3.14, drop `wheel`/`toml`, loosen dependency caps, optional URL extras, `py.typed` |
| #79 | Permission errors, top-level error handling, `--debug`, exit-code convention, `list --json` |

Also in this phase: one module for text/Markdown/HTML conversion, introduced with #76.

## Phase 2: Fast read backend

Adopt apple-notes-parser behind the backend interface (#70). This fixes or unblocks:

- #22: folder lookups are slow
- #4: subfolders can't be read
- #56: reading tags
- #71 (and finishes #75): detecting notes that aren't plain text before a lossy write
- #31: detecting locked notes. They can be detected, but not read without the password.
- #19: a real query API instead of raw predicates

Risk: Notes keeps the store in WAL mode. Opening it read-only the wrong way (for example with `immutable=1`) silently returns stale data, so this needs tests against checked-in fixture databases.

## Phase 3: Write-path quality

Still on AppleScript and ScriptingBridge.

- #39 and #37: `make_note(format=...)` accepts text, Markdown, or HTML
- #13: title style
- #51: `append`, guarded by #71
- #64: attachments on Sequoia and Tahoe (closes #15)
- #4: folder paths for creating notes and moving them into subfolders
- Spike: run Shortcuts actions through the `shortcuts` CLI. "Append to Note" may append without losing formatting, and Shortcuts may also be able to add tags (#56) and create checklists (#29), which AppleScript can't. Not yet verified on macOS 27.

## Phase 4: Features on the fast read path

- #23: `export`, including a SQLite dump (formerly #20)
- #28: `import`
- #5: `notes view`
- #7: TUI. This becomes practical once reads come from the database instead of Apple Events.
- #6: document that `--url` notes are always HTML

## Phase 5: Distribution

- #48: build the standalone binary with PyApp instead of PyInstaller
- A tagged-release GitHub Action that builds the sdist and wheel, publishes to PyPI with trusted publishing, and attaches the binary
- Update the Homebrew formula, which currently declares an unneeded dependency on `python@3.12`

## Parallel track

- #32: the private-framework spike described above. It runs alongside Phases 1 and 2, and its result feeds into #23.
