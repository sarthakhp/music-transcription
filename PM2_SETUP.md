# PM2 Server Management Guide

Easy start/stop/logs management for the Music Transcription API server.

## 🚀 Quick Start (Terminal UI - Recommended)

### Launch the Interactive Terminal Menu

```bash
./server.sh
```

This opens a clean, interactive menu with all server controls:
- Start/Stop/Restart Server
- View Live Logs
- Check Status
- No button limits, no dialogs!

---

## 📦 Installation (One-time setup)

### 1. Install PM2

PM2 requires Node.js. If you don't have it:
```bash
# Install Node.js via Homebrew (macOS)
brew install node

# Or download from: https://nodejs.org/
```

Install PM2 globally:
```bash
npm install -g pm2
```

### 2. Run the Server

**Start the server:**
```bash
./start-server.sh
```
- Server starts in the background
- Logs are displayed (Ctrl+C to exit, server keeps running)
- Server automatically restarts if it crashes

**Stop the server:**
```bash
./stop-server.sh
```

**View logs:**
```bash
./logs-server.sh
```

---

## 📋 PM2 Commands

You can also use PM2 directly:

```bash
# Start server
pm2 start ecosystem.config.js

# Stop server
pm2 stop music-api
pm2 delete music-api  # Stop and remove from PM2

# View logs
pm2 logs music-api              # Live logs
pm2 logs music-api --lines 200  # Last 200 lines

# Server status
pm2 status                      # List all PM2 processes
pm2 describe music-api          # Detailed info

# Monitoring
pm2 monit                       # Real-time dashboard (CPU, memory, logs)

# Restart server (reload code changes)
pm2 restart music-api

# Clear logs
pm2 flush music-api
```

---

## 🔧 Configuration

Server settings are in `ecosystem.config.js`:
- **Interpreter**: Python 3
- **Auto-restart**: Enabled (restarts on crash)
- **Logs**: Stored in `logs/pm2-*.log`
- **Watch mode**: Disabled (change `watch: true` to auto-reload on code changes)

---

## 🐛 Troubleshooting

### Server won't start
```bash
# Check PM2 status
pm2 status

# View error logs
pm2 logs music-api --err

# Check if port 8000 is already in use
lsof -i :8000

# Restart PM2 daemon
pm2 kill
pm2 start ecosystem.config.js
```

### Can't find PM2 command
```bash
# Verify PM2 is installed
npm list -g pm2

# Reinstall if needed
npm install -g pm2
```

### Virtual environment issues
PM2 uses the system's `python3` interpreter. Make sure your dependencies are installed globally or configure the interpreter path in `ecosystem.config.js`:

```javascript
interpreter: '/path/to/your/venv/bin/python3',
```

---

## 📊 Log Files

- **Application logs**: `logs/api.log` (configured in your app)
- **PM2 stdout**: `logs/pm2-out.log`
- **PM2 stderr**: `logs/pm2-error.log`
- **PM2 combined**: `logs/pm2-combined.log`

---

## 🎯 Benefits Over Manual Running

| Feature | Manual (`python run_api.py`) | PM2 |
|---------|------------------------------|-----|
| Background process | ❌ Requires terminal open | ✅ Runs in background |
| Survives terminal close | ❌ Dies with terminal | ✅ Keeps running |
| Auto-restart on crash | ❌ Manual restart needed | ✅ Automatic |
| Log persistence | ❌ Lost on close | ✅ Saved to files |
| Easy log viewing | ❌ Only in terminal | ✅ `pm2 logs` anytime |
| Process monitoring | ❌ Manual | ✅ `pm2 monit` |
| Startup on boot | ❌ Manual | ✅ `pm2 startup` (optional) |

---

## 🔄 Auto-start on System Boot (Optional)

To start the server automatically when your Mac boots:

```bash
# Generate startup script
pm2 startup

# Save current PM2 process list
pm2 save

# Now the server will start automatically on reboot
```

To disable auto-start:
```bash
pm2 unstartup
```

---

## 📚 Learn More

- PM2 Documentation: https://pm2.keymetrics.io/docs/usage/quick-start/
- PM2 Process Management: https://pm2.keymetrics.io/docs/usage/process-management/
