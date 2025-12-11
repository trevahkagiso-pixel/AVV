#!/bin/bash
# Start all three dashboard services

set -e

cd /workspaces/AVV

echo "🚀 Starting Unified Dashboard Services"
echo "════════════════════════════════════════"
echo ""

# Kill existing processes if running
pkill -f "web_ui.py\|ob_ui.py\|unified_ui.py" 2>/dev/null || true
sleep 1

# Start Ichimoku UI (Port 5000)
echo "📊 Starting Ichimoku UI (Port 5000)..."
python3 web_ui.py --port 5000 > web_ui.log 2>&1 &
ICHIMOKU_PID=$!
echo "   PID: $ICHIMOKU_PID"

# Start Order Block UI (Port 5001)
echo "🔲 Starting Order Block UI (Port 5001)..."
python3 ob_ui.py --port 5001 > ob_ui.log 2>&1 &
OB_PID=$!
echo "   PID: $OB_PID"

# Start Unified Dashboard (Port 5002)
echo "📋 Starting Unified Dashboard (Port 5002)..."
python3 unified_ui.py --port 5002 > unified_ui.log 2>&1 &
UNIFIED_PID=$!
echo "   PID: $UNIFIED_PID"

# Wait for services to start
sleep 3

echo ""
echo "✅ All services started!"
echo "════════════════════════════════════════"
echo ""
echo "📌 ACCESS URLs:"
echo "   🎯 Unified Dashboard: http://127.0.0.1:5002"
echo "   📊 Ichimoku UI:       http://127.0.0.1:5000"
echo "   🔲 Order Block UI:    http://127.0.0.1:5001"
echo "   ⚙️  Admin Panel:      http://127.0.0.1:5002/admin"
echo ""
echo "📋 LOGS:"
echo "   tail -f web_ui.log"
echo "   tail -f ob_ui.log"
echo "   tail -f unified_ui.log"
echo ""
echo "🛑 To stop services:"
echo "   pkill -f 'web_ui.py|ob_ui.py|unified_ui.py'"
echo ""

# Keep script running to show logs
wait
