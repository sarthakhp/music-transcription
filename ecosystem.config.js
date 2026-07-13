module.exports = {
  apps: [
    {
      name: 'music-api',
      script: 'run_api.py',
      interpreter: 'python3',
      
      // Working directory (project root)
      cwd: './',
      
      // Environment variables (can override .env file)
      env: {
        PYTHONUNBUFFERED: '1',  // Ensure logs are not buffered
      },
      
      // Instances & execution mode
      instances: 1,
      exec_mode: 'fork',
      
      // Auto-restart configuration
      autorestart: true,
      watch: false,  // Set to true if you want auto-reload on file changes
      max_restarts: 10,
      min_uptime: '10s',  // Minimum uptime before considering it a successful start
      
      // Logging
      error_file: './logs/pm2-error.log',
      out_file: './logs/pm2-out.log',
      log_file: './logs/pm2-combined.log',
      time: true,  // Prefix logs with timestamp
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      
      // Advanced settings
      kill_timeout: 5000,  // Time to wait for graceful shutdown before SIGKILL
      listen_timeout: 3000,  // Time to wait for app to be ready
      shutdown_with_message: false,
    }
  ]
};
