#!/bin/bash
# Manual trigger for testing the digest pipeline
set -euo pipefail

PROJECT_DIR="/Users/gavin/Desktop/ultraplan"
cd "$PROJECT_DIR"

echo "Running AI Digest manually..."
"$PROJECT_DIR/.venv/bin/python" -m src.main

echo ""
echo "Done. Check logs at: $PROJECT_DIR/logs/"
