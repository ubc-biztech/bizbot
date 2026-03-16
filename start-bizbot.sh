#!/bin/bash
# Wrapper script for BizBot - ensures clean start every time
# PM2 calls this script, which handles cleanup before starting the app

set -e

echo "[WRAPPER] Starting BizBot with cleanup..."

# Kill any existing Python processes running main.py (except this wrapper)
echo "[WRAPPER] Cleaning up old processes..."
pkill -9 -f "python main.py" 2>/dev/null || true

# Wait for cleanup
sleep 1

# Double check
REMAINING=$(pgrep -f "python main.py" 2>/dev/null | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "[WRAPPER] Found $REMAINING lingering processes, force killing..."
    pkill -9 -f "python main.py" 2>/dev/null || true
    sleep 1
fi

echo "[WRAPPER] Starting application..."

# Start the actual application
exec uv run python main.py
