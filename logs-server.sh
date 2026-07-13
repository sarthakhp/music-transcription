#!/bin/bash

# View live logs from the Music Transcription API server

echo "📋 Viewing Music Transcription API logs..."
echo "   (Press Ctrl+C to exit, server keeps running)"
echo ""

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 is not installed!"
    exit 1
fi

# Show live logs
pm2 logs music-api --lines 100
