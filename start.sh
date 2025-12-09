#!/bin/bash
set -e

echo "=== Starting Xvfb ==="
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac +extension GLX +render -noreset &
XVFB_PID=$!
echo "Xvfb started with PID $XVFB_PID"

# Xvfb'nin başlamasını bekle
sleep 5

# Verify Xvfb is running
if ! ps -p $XVFB_PID > /dev/null; then
    echo "ERROR: Xvfb failed to start!"
    exit 1
fi

echo "=== Xvfb is running ==="
echo "=== Starting Flask Dashboard ==="
cd /app
exec python dashboard.py
