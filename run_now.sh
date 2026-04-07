#!/bin/bash
# Manual trigger for testing the digest pipeline
set -euo pipefail

PROJECT_DIR="/Users/gavin/Desktop/Organized/projects/business/twitter-email-bot"
cd "$PROJECT_DIR"

echo "Running AI Digest manually..."
# caffeinate -s keeps the system awake during the run
caffeinate -s "$PROJECT_DIR/.venv/bin/python" -m src.main

echo ""
echo "Done. Check logs at: $PROJECT_DIR/logs/"
