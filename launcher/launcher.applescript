-- Student Feedback launcher: starts the feedback app + local AI (light mode, no Course Hub) and opens the page.
-- If it is already running, offers to open it or stop it (stopping frees the memory the AI model uses).
property startScript : "/Users/shingokawamura/Repos-folder/student-feedback/start.sh"
property pageURL : "http://127.0.0.1:8765"

on run
	set isRunning to false
	try
		set isRunning to ((do shell script "/usr/sbin/lsof -tiTCP:8765 -sTCP:LISTEN || true") is not "")
	end try

	if isRunning then
		try
			set choice to button returned of (display dialog "Student Feedback is running." & return & return & "Stop it when you are finished to free up memory." buttons {"Stop", "Cancel", "Open"} default button "Open" cancel button "Cancel" with title "Student Feedback" with icon note)
		on error
			return -- Cancel
		end try
		if choice is "Open" then
			open location pageURL
		else if choice is "Stop" then
			try
				do shell script "mkdir -p /tmp/rcs-logs; " & quoted form of startScript & " stop > /tmp/rcs-logs/launcher.log 2>&1"
				display notification "Stopped the app and the local AI." with title "Student Feedback"
			on error errMsg
				display dialog "Could not stop it cleanly:" & return & errMsg buttons {"OK"} default button "OK" with title "Student Feedback" with icon caution
			end try
		end if
	else
		display notification "Starting. This can take up to a minute." with title "Student Feedback"
		try
			do shell script "mkdir -p /tmp/rcs-logs; NO_BROWSER=1 " & quoted form of startScript & " > /tmp/rcs-logs/launcher.log 2>&1"
			open location pageURL
			display notification "Ready. Use this icon again to stop it when you are done." with title "Student Feedback"
		on error errMsg
			display dialog "Student Feedback could not start." & return & return & "Details are in /tmp/rcs-logs/launcher.log" & return & errMsg buttons {"OK"} default button "OK" with title "Student Feedback" with icon caution
		end try
	end if
end run
