(********* AppleScript handlers for macnotesapp *********)

(*
This file is loaded by macnotesapp/script_loader.py and must be saved as UTF-8.
Handlers are called from Python with run_script(handlerName, args...).

Handler names follow the pattern <object><Action>, for example noteGetBody(accountName, noteID).

Reads go through ScriptingBridge where possible; these handlers are the fallback
for cases where ScriptingBridge returns bad data and the main path for writes.
Notes.app's AppleScript dictionary is buggy on some macOS versions, which explains
some of the workarounds below.
*)

property WAIT_FOR_SCRIPT : 0.05

(******** NotesApp Class *********)

on notesActivate()
	(* Activate Notes *)
	tell application "Notes"
		activate
	end tell
end notesActivate

on notesQuit()
	(* Quit Notes *)
	tell application "Notes"
		quit
	end tell
end notesQuit

on notesGetAccounts()
	(* Get names of all Notes accounts *)
	tell application "Notes"
		return name of accounts
	end tell
end notesGetAccounts

(********** Note Class *********)

on noteGetName(accountName, noteID)
	(* Get name of noteID in accountName *)
	tell application "Notes"
		tell account accountName
			return name of note id (noteID)
		end tell
	end tell
end noteGetName

on noteSetName(accountName, noteID, noteName)
	(* Set name of noteID in accountName *)
	tell application "Notes"
		tell account accountName
			set name of note id (noteID) to noteName
		end tell
	end tell
end noteSetName

on noteGetAccount(noteID)
	(* Get account that note belongs to *)
	-- This is a hack but best I can think of
	-- Try every account to find the one the note belongs to
	set allAccounts to notesGetAccounts()
	delay WAIT_FOR_SCRIPT
	tell application "Notes"
		repeat with accountName in allAccounts
			tell account accountName
				try
					-- this will result in error if noteID doesn't belong to accountName
					set noteRecord to note id noteID
					return accountName as string
				end try
			end tell
		end repeat
	end tell
	return 0
end noteGetAccount

on noteGetContainer(accountName, noteID)
	(* Get container (folder) name of noteID in accountName *)
	tell application "Notes"
		tell account accountName
			set noteContainerID to «class seld» of ((container of note id noteID) as record)
			set noteFolderName to name of (first folder whose id is noteContainerID)
			return noteFolderName
		end tell
	end tell
end noteGetContainer

on noteGetBody(accountName, noteID)
	(* Get body (as HTML) of noteID in accountName *)
	tell application "Notes"
		tell account accountName
			return body of note id (noteID)
		end tell
	end tell
end noteGetBody

on noteSetBody(accountName, noteID, noteBody)
	(* Set body (as HTML) of noteID in accountName *)
	tell application "Notes"
		tell account accountName
			set body of note id (noteID) to noteBody
		end tell
	end tell
end noteSetBody

on noteGetPlainText(accountName, noteID)
	(* Get plain text contents of noteID in accountName *)
	tell application "Notes"
		tell account accountName
			return plaintext of note id (noteID)
		end tell
	end tell
end noteGetPlainText

on noteGetCreationDate(accountName, noteID)
	(*Get creation date of noteID in accountName *)
	tell application "Notes"
		tell account accountName
			return creation date of note id (noteID)
		end tell
	end tell
end noteGetCreationDate

on noteGetModificationDate(accountName, noteID)
	(* Get modification date of noteID in accountName *)
	tell application "Notes"
		tell account accountName
			return modification date of note id (noteID)
		end tell
	end tell
end noteGetModificationDate

on noteGetPasswordProtected(accountName, noteID)
	(* Get password protected status of noteID in accountName *)
	tell application "Notes"
		tell account accountName
			return password protected of note id (noteID)
		end tell
	end tell
end noteGetPasswordProtected

on noteShow(accountName, noteID)
	(* show note in Notes UI *)
	tell application "Notes"
		tell account accountName
			show note id (noteID)
		end tell
	end tell
end noteShow

on noteAddAttachment(accountName, noteID, attachmentPath)
	(* Add file at attachmentPath to noteID; returns id of new attachment *)
	tell application "Notes"
		tell account accountName
			set theNote to note id (noteID)
			set theAttachment to make new attachment at theNote with data POSIX file attachmentPath
			return id of theAttachment
		end tell
	end tell
end noteAddAttachment

(********** Account Class *********)

on accountGetDefaultFolder(accountName)
	(* Get default folder for accountName *)
	tell application "Notes"
		repeat with accountRecord in accounts
			if name of accountRecord = accountName then
				return name of default folder of accountRecord
			end if
		end repeat
	end tell
	return 0
end accountGetDefaultFolder

on accountGetFolderNames(accountName)
	(* Get folders in accountName *)
	tell application "Notes"
		repeat with accountRecord in accounts
			if name of accountRecord = accountName then
				return name of every folder of accountRecord
			end if
		end repeat
	end tell
	return 0
end accountGetFolderNames

on accountGetFolderTree(accountName)
	(* Get {ids, names, parent folder ids} of every folder in accountName, including
	subfolders; the parent id of a top-level folder is "" *)
	tell application "Notes"
		tell account accountName
			set folderIDs to {}
			set folderNames to {}
			set parentIDs to {}
			repeat with theFolder in every folder
				set end of folderIDs to id of theFolder
				set end of folderNames to name of theFolder
				set theContainer to container of theFolder
				if class of theContainer is folder then
					set end of parentIDs to id of theContainer
				else
					set end of parentIDs to ""
				end if
			end repeat
			return {folderIDs, folderNames, parentIDs}
		end tell
	end tell
end accountGetFolderTree

on accountShow(accountName)
	(* Show account in Notes UI *)
	tell application "Notes"
		tell account accountName
			show
		end tell
	end tell
end accountShow

on accountID(accountName)
	(* ID of accountName *)
	tell application "Notes"
		tell account accountName
			return its id
		end tell
	end tell
end accountID

(********** Write Operations **********)

on noteDelete(noteID)
	(* Delete note with noteID *)
	tell application "Notes"
		set theNote to first note whose id is noteID
		delete theNote
	end tell
end noteDelete

on noteMoveToFolder(accountName, noteID, folderID)
	(* Move noteID to the folder with folderID, which may be a subfolder *)
	tell application "Notes"
		tell account accountName
			move note id noteID to folder id folderID
		end tell
	end tell
end noteMoveToFolder

on folderCreate(accountName, folderName)
	(* Create new top-level folder in account; returns id of new folder *)
	tell application "Notes"
		tell account accountName
			set newFolder to make new folder with properties {name:folderName}
			return id of newFolder
		end tell
	end tell
end folderCreate

on folderCreateIn(accountName, parentID, folderName)
	(* Create new folder inside the folder with parentID; returns id of new folder *)
	tell application "Notes"
		tell account accountName
			set newFolder to make new folder at folder id parentID with properties {name:folderName}
			return id of newFolder
		end tell
	end tell
end folderCreateIn

on folderDelete(accountName, folderID)
	(* Delete the folder with folderID; Notes leaves its subfolders behind, so delete those first *)
	tell application "Notes"
		tell account accountName
			delete folder id folderID
		end tell
	end tell
end folderDelete
