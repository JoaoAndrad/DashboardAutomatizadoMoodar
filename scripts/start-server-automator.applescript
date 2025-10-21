-- Automator / AppleScript example: create an Automator "Application" that runs this script.
-- It will open Terminal and execute the starter, keeping the terminal open.
on run
    set projectPath to POSIX path of ("/PATH/TO/PROJECT" as string)
    tell application "Terminal"
        activate
        do script "cd \"" & projectPath & "\"; ./scripts/start-server-mac.sh"
    end tell
end run

-- Replace /PATH/TO/PROJECT with the absolute path, save as an Automator Application.
