#!/bin/bash

# Stop the Music Transcription API server

echo "🛑 Stopping Music Transcription API server..."

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 is not installed!"
    exit 1
fi

# Stop and delete the server process
pm2 delete music-api

if [ $? -eq 0 ]; then
    echo "✅ Server stopped successfully!"
else
    echo "⚠️  Server was not running or already stopped"
fi
