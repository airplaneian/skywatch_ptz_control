osascript -e 'tell app "Terminal"
    do script "cd \"/Users/iservin/Documents/skywatch_ptz_control\" && ./.venv/bin/python app.py"
    activate
end tell'
