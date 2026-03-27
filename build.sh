#!/bin/bash
set -e

echo "🌊 Building StreamContext v2.0..."

# Generate icons
echo "📦 Generating icons..."
python3 /Users/hive_mind/streamcontext/generate_icons.py 2>/dev/null || echo "Icons skipped"

# Kill old service
echo "🔄 Killing old service..."
pkill -f "streamcontext.*main.py" 2>/dev/null || true
lsof -ti:7892 | xargs kill -9 2>/dev/null || true
sleep 1

# Install deps
echo "📦 Installing deps..."
pip3 install fastapi uvicorn "anthropic>=0.50.0" python-dotenv aiosqlite --break-system-packages -q

# Start new service
echo "🚀 Starting service..."
mkdir -p /Users/hive_mind/.streamcontext/logs
cd /Users/hive_mind/streamcontext/service
nohup python3 main.py > /Users/hive_mind/.streamcontext/logs/service.log 2>&1 &

sleep 3

# Verify
if curl -s http://localhost:7892/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✅ Service v{d[\"version\"]} running — {d[\"conversations\"]} conversations')"; then
    echo ""
    echo "🎉 StreamContext v2.0 is LIVE!"
    echo "📍 Archive: http://localhost:7892"
else
    echo "⚠️ Service starting... check logs:"
    tail -20 /Users/hive_mind/.streamcontext/logs/service.log
fi
