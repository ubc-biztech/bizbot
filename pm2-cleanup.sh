#!/bin/bash
# PM2 pre-restart hook - kills any lingering processes
# This runs automatically before PM2 starts/restarts the app

echo "[CLEANUP] Killing lingering BizBot processes..."

# Kill any Python processes running main.py
pkill -9 -f "python main.py" 2>/dev/null || true
pkill -9 -f "uv run python main.py" 2>/dev/null || true

# Wait a moment for cleanup
sleep 1

# Verify cleanup
REMAINING=$(pgrep -f "python main.py" 2>/dev/null | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "[CLEANUP] WARNING: Found $REMAINING remaining processes, killing again..."
    pkill -9 -f "python main.py" 2>/dev/null || true
    pkill -9 -f "uv run python main.py" 2>/dev/null || true
    sleep 1
fi

echo "[CLEANUP] Cleanup complete"
exit 0
