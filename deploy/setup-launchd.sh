#!/bin/bash
# Setup script for launchd scheduling on macOS
# Run this script to install the prediction scheduler

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_NAME="com.perpetual-predict.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "=== Perpetual Predict Scheduler Setup ==="
echo ""

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"
echo "Created logs directory: $PROJECT_DIR/logs"

# Check if Claude CLI is available
if ! command -v claude &> /dev/null; then
    echo "ERROR: 'claude' command not found in PATH"
    echo "Please ensure Claude Code CLI is installed and in your PATH"
    exit 1
fi
echo "Claude CLI found: $(which claude)"

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "ERROR: 'uv' command not found in PATH"
    echo "Please ensure uv is installed: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo "uv found: $(which uv)"

# Test the cycle command
echo ""
echo "Testing cycle command (dry run)..."
cd "$PROJECT_DIR"
uv run python -m perpetual_predict cycle --help
echo "Cycle command works!"

# Copy plist file
echo ""
echo "Installing launchd plist..."
cp "$PLIST_SOURCE" "$PLIST_DEST"
echo "Copied to: $PLIST_DEST"

# Unload if already loaded
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# Load the service
launchctl load "$PLIST_DEST"
echo "Service loaded!"

# Check status
echo ""
echo "=== Service Status ==="
launchctl list | grep perpetual-predict || echo "Service registered (waiting for scheduled time)"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "The scheduler will run at these times (KST):"
echo "  01:01, 05:01, 09:01, 13:01, 17:01, 21:01"
echo ""
echo "Commands:"
echo "  Check logs:       tail -f $PROJECT_DIR/logs/launchd.log"
echo "  Check errors:     tail -f $PROJECT_DIR/logs/launchd.err"
echo "  Manual run:       launchctl start com.perpetual-predict"
echo "  Stop service:     launchctl unload $PLIST_DEST"
echo "  Restart service:  launchctl unload $PLIST_DEST && launchctl load $PLIST_DEST"
echo ""
echo "IMPORTANT: Keep your Mac awake or enable 'Wake for network access' in"
echo "System Preferences > Battery > Options"
