#!/bin/bash
# StreamContext — Mac Auto-Start Setup
# Run this once to have StreamContext start automatically on login

PLIST="$HOME/Library/LaunchAgents/ai.streamcontext.service.plist"
SERVICE_DIR="$HOME/streamcontext/service"
LOG_DIR="$HOME/.streamcontext/logs"

mkdir -p "$LOG_DIR"

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>ai.streamcontext.service</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/python3</string>
        <string>$SERVICE_DIR/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SERVICE_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/service.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/service-error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

# Load it
launchctl load "$PLIST" 2>/dev/null || true
launchctl start ai.streamcontext.service 2>/dev/null || true

echo "✅ StreamContext will now start automatically on login!"
echo "📍 Service: http://localhost:7892"
echo ""
echo "To stop auto-start:"
echo "  launchctl unload ~/Library/LaunchAgents/ai.streamcontext.service.plist"
