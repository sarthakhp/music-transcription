#!/usr/bin/env python3
"""
Music Transcription API Server Control - Terminal UI
A simple, interactive terminal interface for managing the server with PM2
"""

import subprocess
import sys
import os
from pathlib import Path


def clear_screen():
    """Clear the terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')


def print_header():
    """Print the application header"""
    print("=" * 60)
    print("🎵  Music Transcription API Server Control")
    print("=" * 60)
    print()


def get_server_status():
    """Check if the server is running via PM2"""
    try:
        result = subprocess.run(
            ['pm2', 'list'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if 'music-api' in result.stdout:
            if 'online' in result.stdout:
                return "✅ Running", "online"
            elif 'stopped' in result.stdout:
                return "🛑 Stopped", "stopped"
            elif 'errored' in result.stdout:
                return "❌ Error", "errored"
            else:
                return "⚠️  Unknown", "unknown"
        else:
            return "⚪ Not Running", "not_running"
    except subprocess.TimeoutExpired:
        return "⏱️  Timeout", "timeout"
    except FileNotFoundError:
        return "❌ PM2 Not Installed", "no_pm2"
    except Exception as e:
        return f"❌ Error: {str(e)}", "error"


def start_server():
    """Start the server using PM2"""
    print("\n🚀 Starting server...")
    print("-" * 60)
    
    try:
        result = subprocess.run(
            ['./start-server.sh'],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Server started successfully!")
        else:
            print("❌ Failed to start server")
            if result.stderr:
                print(f"Error: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⏱️  Command timed out (server might still be starting...)")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("-" * 60)
    input("\nPress Enter to continue...")


def stop_server():
    """Stop the server using PM2"""
    print("\n🛑 Stopping server...")
    print("-" * 60)
    
    try:
        result = subprocess.run(
            ['./stop-server.sh'],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ Server stopped successfully!")
        else:
            print("⚠️  Server stop command executed")
            if result.stdout:
                print(result.stdout)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("-" * 60)
    input("\nPress Enter to continue...")


def view_logs():
    """View server logs in real-time"""
    print("\n📋 Opening logs (Press Ctrl+C to exit logs)...")
    print("-" * 60)
    print()
    
    try:
        subprocess.run(
            ['pm2', 'logs', 'music-api', '--lines', '50'],
            cwd=Path(__file__).parent
        )
    except KeyboardInterrupt:
        print("\n\nExiting logs...")
    except Exception as e:
        print(f"❌ Error: {e}")
        input("\nPress Enter to continue...")


def show_detailed_status():
    """Show detailed server status"""
    print("\n📊 Server Status")
    print("-" * 60)
    
    try:
        subprocess.run(['pm2', 'describe', 'music-api'])
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("-" * 60)
    input("\nPress Enter to continue...")


def main():
    """Main application loop"""
    while True:
        clear_screen()
        print_header()
        
        # Show current status
        status_text, status_code = get_server_status()
        print(f"Status: {status_text}")
        print()
        print("-" * 60)
        print()
        
        # Show menu
        print("Choose an action:")
        print()
        print("  1. Start Server")
        print("  2. Stop Server")
        print("  3. View Logs")
        print("  4. Detailed Status")
        print("  5. Restart Server")
        print("  0. Exit")
        print()
        print("-" * 60)
        
        choice = input("\nEnter your choice (0-5): ").strip()
        
        if choice == '1':
            start_server()
        elif choice == '2':
            stop_server()
        elif choice == '3':
            view_logs()
        elif choice == '4':
            show_detailed_status()
        elif choice == '5':
            print("\n🔄 Restarting server...")
            try:
                subprocess.run(['pm2', 'restart', 'music-api'])
                print("✅ Server restarted!")
            except Exception as e:
                print(f"❌ Error: {e}")
            input("\nPress Enter to continue...")
        elif choice == '0':
            print("\n👋 Goodbye!\n")
            sys.exit(0)
        else:
            print("\n❌ Invalid choice. Please enter a number between 0 and 5.")
            input("\nPress Enter to continue...")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)
