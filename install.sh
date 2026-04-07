#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/gavin/Desktop/ultraplan"
PLIST_NAME="com.ultraplan.digest.plist"
KEEPAWAKE_PLIST="com.ultraplan.keepawake.plist"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "=== UltraPlan AI Digest Installer ==="
echo ""

# 1. Check .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in your details."
    exit 1
fi

# 2. Create venv if needed
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/.venv"
fi

# 3. Install dependencies
echo "Installing dependencies..."
"$PROJECT_DIR/.venv/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt"

# 4. Create data and log directories
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/logs"

# 5. Run tests
echo "Running tests..."
cd "$PROJECT_DIR"
if ! "$PROJECT_DIR/.venv/bin/python" -m pytest tests/ -q; then
    echo "ERROR: Tests failed. Fix before installing."
    exit 1
fi
echo ""

# 6. Unload existing plists if present
for label in "com.ultraplan.digest" "com.ultraplan.keepawake"; do
    if launchctl list 2>/dev/null | grep -q "$label"; then
        echo "Unloading existing $label..."
        launchctl unload "$LAUNCH_AGENTS/${label}.plist" 2>/dev/null || true
    fi
done

# 7. Install keepawake agent (persistent caffeinate to prevent sleep)
cat > "$LAUNCH_AGENTS/$KEEPAWAKE_PLIST" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ultraplan.keepawake</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-s</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
PLIST
echo "Installed keepawake agent (prevents sleep when on power)"

# 8. Copy digest plist to LaunchAgents
echo "Installing digest launchd plist..."
cp "$PROJECT_DIR/$PLIST_NAME" "$LAUNCH_AGENTS/$PLIST_NAME"

# 9. Load both plists
echo "Loading launchd plists..."
launchctl load "$LAUNCH_AGENTS/$KEEPAWAKE_PLIST"
launchctl load "$LAUNCH_AGENTS/$PLIST_NAME"

# 10. Schedule wake-from-sleep as belt-and-suspenders
# (in case caffeinate is somehow killed)
echo ""
echo "Setting up wake schedules (requires admin password)..."
sudo pmset repeat wakeorpoweron MTWRFSU 07:55:00 wakeorpoweron MTWRFSU 17:55:00 2>/dev/null && \
    echo "Wake schedules set: 7:55 AM and 5:55 PM daily" || \
    echo "WARNING: Could not set wake schedules (non-fatal, caffeinate handles this)"

echo ""
echo "=== Installation Complete ==="
echo "Recipients: $(cat "$PROJECT_DIR/.env")"
echo "Schedule: 8:00 AM and 6:00 PM daily"
echo "Sleep prevention: caffeinate agent + wake schedules"
echo "Logs: $PROJECT_DIR/logs/"
echo "Database: $PROJECT_DIR/data/articles.db"
echo ""
echo "To test now:  bash $PROJECT_DIR/run_now.sh"
echo "To uninstall:"
echo "  launchctl unload ~/Library/LaunchAgents/$PLIST_NAME"
echo "  launchctl unload ~/Library/LaunchAgents/$KEEPAWAKE_PLIST"
echo "  sudo pmset repeat cancel"
echo ""
echo "IMPORTANT: The first run will trigger a macOS Automation permission prompt."
echo "You must click 'OK' to allow Terminal/Python to control Messages.app."
echo ""
echo "FOR LID-CLOSED OPERATION: Keep your Mac plugged into power."
echo "The keepawake agent prevents sleep. Close the lid — it still runs."
