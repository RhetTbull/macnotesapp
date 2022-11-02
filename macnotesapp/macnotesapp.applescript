(********* AppleScript for macnotesapp  *********)

(*
Note: the AppleScript interface for Notes on Catalina (10.15.x) is pretty buggy.  

See for example:
- https://talk.automators.fm/t/applescript-error-catalina/5880/7
- https://hookproductivity.com/help/integration/using-hook-with-apple-notes/hook-and-macos-10-15-catalina-notes-app/

Unfortanately, my Mac runs Catalina and so I can't fully develop this until I upgrade. I've done the best I can to work around some of these bugs so some of the methods are a little hacky but they do work.
*)

property WAIT_FOR_SCRIPT : 0.05

(******** NotesApp Class *********)

on notesActivate()
	(* Quit Notes *)
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

on notesVersion()
	(* Get Notes version *)
	tell application "Notes"
		return its version
	end tell
end notesVersion

on notesGetAllNotes()
	(* Get IDs for all notes
	
	Returns:
		list of lists in form {{account, {note ids}, ...}
	*)
	set allNotes to {}
	set accountNames to notesGetAccounts()
	delay WAIT_FOR_SCRIPT
	tell application "Notes"
		repeat with accountName in accountNames
			tell account accountName
				set allNotes to allNotes & {{accountName as string, id of notes}}
			end tell
		end repeat
	end tell
	return allNotes
end notesGetAllNotes

on notesGetCount()
	(* Get count of all notes *)
	set notesCount to 0
	set accountNames to notesGetAccounts()
	delay WAIT_FOR_SCRIPT
	tell application "Notes"
		repeat with accountName in accountNames
			tell account accountName
				set notesCount to notesCount + (count of notes)
			end tell
		end repeat
	end tell
	return notesCount
end notesGetCount

on notesGetSelected()
	(* Get ids of selected note
	
	Returns:
		list of lists in form {{account, noteid}, ...}
	*)
	set selectedIDs to {}
	tell application "Notes"
		set theSelection to selection
		repeat with theNote in theSelection
			set noteID to «class seld» of (theNote as record)
			copy noteID to end of selectedIDs
		end repeat
	end tell
	set theSelection to {}
	repeat with noteID in selectedIDs
		set theAccount to noteGetAccount(noteID)
		delay WAIT_FOR_SCRIPT
		copy {theAccount, noteID as string} to end of theSelection
	end repeat
	return theSelection
end notesGetSelected

on notesFindWithName(nameText)
	(* Find notes with name containing nameText
	
	Args:
		nameText: string to search for in note name
		
	Returns:
		List of lists in form {{accountName, noteID}, ...}
	*)
	set notesResults to {}
	set accountNames to notesGetAccounts()
	delay WAIT_FOR_SCRIPT
	tell application "Notes"
		repeat with accountName in accountNames
			tell account accountName
				set matchingNotes to (id of every note where name contains nameText)
				set notesResults to notesResults & {{accountName as string, matchingNotes}}
			end tell
		end repeat
	end tell
	return notesResults
end notesFindWithName

on notesFindWithText(noteText)
	(* Find notes with body containing noteText
	
	Args:
		noteText: string to search for in note name
		
	Returns:
		List of lists in form {{accountName, noteID}, ...}
	*)
	set notesResults to {}
	set accountNames to notesGetAccounts()
	delay WAIT_FOR_SCRIPT
	tell application "Notes"
		repeat with accountName in accountNames
			tell account accountName
				set matchingNotes to (id of every note where plaintext contains noteText)
				set notesResults to notesResults & {{accountName as string, matchingNotes}}
			end tell
		end repeat
	end tell
	return notesResults
end notesFindWithText

on notesGetDefaultAccount()
	(* Get name of default account *)
	tell application "Notes"
		return name of default account
	end tell
end notesGetDefaultAccount

on notesGetAccounts()
	(* Get names of all Notes accounts *)
	tell application "Notes"
		return name of accounts
	end tell
end notesGetAccounts

on notesMakeNoteWithAccount(accountName, folderName, noteName, noteBody)
	(* Create a new note in specified account and folder
	
	Args:
		accountName: name of account to create note in
		folderName: name of folder in account to create note in
		noteName: name of new note
		noteBody: body of new note
		
	Returns:
		id of newly created note or 0 if error
	*)
	tell application "Notes"
		tell account accountName
			set theNote to make new note at folder folderName with properties {name:noteName, body:noteBody}
			set noteID to «class seld» of (theNote as record)
			return noteID
		end tell
	end tell
end notesMakeNoteWithAccount

on notesMakeNote(noteName, noteBody)
	(* Create note in default folder of default account
	
	Args:
		noteName: name of new note
		noteBody: body of new note
		
	Returns:
		id of newly created note or 0 if error
	*)
	tell application "Notes"
		try
			set theNote to make new note with properties {name:noteName, body:noteBody}
			set noteID to «class seld» of (theNote as record)
			return noteID
		on error
			return 0
		end try
	end tell
end notesMakeNote

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

(*********** Folder Class *********)

on folderGetName(accountName, folderID)
	(* Get name of folder*)
	tell application "Notes"
		tell account accountName
			set folderName to name of (first folder whose id is folderID)
			return folderName
		end tell
	end tell
end folderGetName

on folderShow(accountName, folderID)
	(* show folder in Notes UI *)
	tell application "Notes"
		tell account accountName
			show folder id (folderID)
		end tell
	end tell
end folderShow

(* BAH! Notes is too damn buggy on Catalina

on folderGetAllNotes(accountName, folderID)
	tell application "Notes"
		tell account accountName
			set theFolder to first folder whose id is folderID
			tell folder theFolder
				set folderNotes to notes of theFolder
				set allNotes to {}
				repeat with theNote in folderNotes
					set noteID to «class seld» of (theNote as record)
					copy noteID to end of allNotes
				end repeat
				return allNotes
			end tell
		end tell
	end tell
end folderGetAllNotes


on folderGetCount(accountName, folderID)
	(* Return count of notes in folder *)
	set folderNotes to folderGetAllNotes(accountName, folderID)
	return count of folderNotes
end folderGetCount


--Does not appear to work on Catalina if in subfolder so defer to later when I have access to Big Sur+ 

on folderGetContainer(accountName, folderID)
	(* Get parent folder for folder *)
	tell application "Notes"
		tell account accountName
			set folderContainerID to «class seld» of ((container of folder id folderID) as record)
			return folderContainerID
		end tell
	end tell
end folderGetContainer

*)

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

on accountGetAllNotes(accountName)
	(* Get all notes for an account
	
	 Args:
	 	accountName: name of account to get notes for
		
	Returns:
		list of note ids in account
	 *)
	set allNotes to {}
	tell application "Notes"
		tell account accountName
			set allNotes to id of notes
		end tell
	end tell
	return allNotes
end accountGetAllNotes

on accountGetCount(accountName)
	(* Return count of notes in account *)
	tell application "Notes"
		tell account accountName
			set theCount to (count of notes)
			return theCount
		end tell
	end tell
end accountGetCount

on accountShow(accountName)
	(* Show account in Notes UI *)
	tell application "Notes"
		tell account accountName
			show
		end tell
	end tell
end accountShow

on accountFindWithName(accountName, nameText)
	(* Find notes in accountName with name containing nameText
	
	Args:
		nameText: string to search for in note name
		
	Returns:
		List of lists in form {{accountName, noteID}, ...}
	*)
	tell application "Notes"
		tell account accountName
			set matchingNotes to (id of every note where name contains nameText)
			return matchingNotes
		end tell
	end tell
end accountFindWithName

on accountFindWithText(accountName, noteText)
	(* Find notes in accountName with body containing noteText
	
	Args:
		noteText: string to search for in note name
		
	Returns:
		List of lists in form {{accountName, noteID}, ...}
	*)
	tell application "Notes"
		tell account accountName
			set matchingNotes to (id of every note where plaintext contains noteText)
			return matchingNotes
		end tell
	end tell
end accountFindWithText

on accountName(accountName)
	(* Get name of account *)
	tell application "Notes"
		tell account accountName
			return its name
		end tell
	end tell
end accountName

on accountID(accountName)
	(* ID of accountName *)
	tell application "Notes"
		tell account accountName
			return its id
		end tell
	end tell
end accountID

(********** Test **********)

