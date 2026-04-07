#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/gavin/Desktop/ultraplan"
PLIST_NAME="com.ultraplan.digest.plist"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "=== UltraPlan AI Digest Installer ==="
echo ""

# 1. Create venv if needed
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/.venv"
fi

# 2. Install dependencies
echo "Installing dependencies..."
"$PROJECT_DIR/.venv/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt"

# 3. Create data and log directories
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/logs"

# 4. Run tests
echo "Running tests..."
cd "$PROJECT_DIR"
if ! "$PROJECT_DIR/.venv/bin/python" -m pytest tests/ -q; then
    echo "ERROR: Tests failed. Fix before installing."
    exit 1
fi
echo ""

# 5. Unload existing plist if present
if launchctl list 2>/dev/null | grep -q "com.ultraplan.digest"; then
    echo "Unloading existing plist..."
    launchctl unload "$LAUNCH_AGENTS/$PLIST_NAME" 2>/dev/null || true
fi

# 6. Copy plist to LaunchAgents
echo "Installing launchd plist..."
cp "$PROJECT_DIR/$PLIST_NAME" "$LAUNCH_AGENTS/$PLIST_NAME"

# 7. Load plist
echo "Loading launchd plist..."
launchctl load "$LAUNCH_AGENTS/$PLIST_NAME"

echo ""
echo "=== Installation Complete ==="
echo "Phone: $(grep 'PHONE_NUMBER' "$PROJECT_DIR/src/config.py" | head -1)"
echo "Schedule: 8:00 AM and 6:00 PM daily"
echo "Logs: $PROJECT_DIR/logs/"
echo "Database: $PROJECT_DIR/data/articles.db"
echo ""
echo "To test now:  bash $PROJECT_DIR/run_now.sh"
echo "To uninstall: launchctl unload ~/Library/LaunchAgents/$PLIST_NAME"
echo ""
echo "IMPORTANT: The first run will trigger a macOS Automation permission prompt."
echo "You must click 'OK' to allow Terminal/Python to control Messages.app."
