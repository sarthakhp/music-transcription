#!/bin/bash

# Start the Music Transcription API server using PM2
# This script starts the server in the background and shows live logs

echo "🚀 Starting Music Transcription API server..."

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 is not installed!"
    echo "📦 Install it with: npm install -g pm2"
    echo "    (Requires Node.js/npm to be installed)"
    exit 1
fi

# Start the server using the ecosystem config
pm2 start ecosystem.config.js

# Check if start was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Server started successfully!"
    echo ""
    echo "📊 Quick commands:"
    echo "   ./logs-server.sh     - View live logs"
    echo "   ./stop-server.sh     - Stop the server"
    echo "   pm2 monit            - Real-time monitoring dashboard"
    echo "   pm2 status           - Check server status"
    echo ""
    echo "📋 Showing logs (Ctrl+C to exit, server keeps running)..."
    echo ""
    sleep 2
    pm2 logs music-api
else
    echo "❌ Failed to start server"
    exit 1
fi
