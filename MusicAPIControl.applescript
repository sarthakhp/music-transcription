-- Music Transcription API Server Control
-- Simple launcher for the Terminal UI

on run
	-- Get the directory containing this app
	tell application "System Events"
		set appPath to POSIX path of (path to me)
	end tell

	-- Extract the directory containing the app
	set AppleScript's text item delimiters to "/"
	set pathItems to text items of appPath
	set projectPath to (items 1 thru -2 of pathItems) as text
	set AppleScript's text item delimiters to "/"
	set projectPath to projectPath & "/"

	-- Launch the terminal UI
	set terminalScript to "cd " & quoted form of projectPath & " && ./server.sh"

	tell application "Terminal"
		activate
		do script terminalScript
	end tell
end run
