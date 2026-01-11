#!/bin/bash
osascript -e 'tell application "Terminal"
    do script "cd \"/Users/iservin/Documents/skywatch_ptz_control\" && ./.venv/bin/python app.py"
    activate
end tell'
sleep 3
open "http://localhost:5001"
