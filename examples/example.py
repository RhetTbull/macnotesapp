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
