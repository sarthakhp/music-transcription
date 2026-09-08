#!/usr/bin/env python3
"""
MusicTranscriber launcher — starts the FastAPI backend and opens the UI.

Invoked by the platform-specific app wrapper:
  macOS  : Contents/MacOS/MusicTranscriber (shell script)
  Windows: MusicTranscriber.exe (compiled wrapper or .bat)
  Linux  : AppRun (shell script)

All three set CWD to the resources directory before calling:
  <bundled-python> launcher.py
"""

import os
import sys
import time
import shlex
import signal
import platform
import subprocess
import urllib.request
from pathlib import Path


# ── Versioning ───────────────────────────────────────────────────────────────
# Bump REQUIREMENTS_VERSION whenever requirements.txt or requirements-api.txt
# change in a way that affects the installed packages.  The setup script writes
# this string to <data_dir>/.requirements_version; if the file is missing or
# contains a different value, first-run setup is triggered again.
REQUIREMENTS_VERSION = "3"

SERVER_PORT = 47821


# ── Path helpers ─────────────────────────────────────────────────────────────

def get_resources() -> Path:
    """Directory that holds python/, backend/, web/, ffmpeg next to this script."""
    return Path(__file__).parent.resolve()


def get_data_dir() -> Path:
    """Platform-appropriate user data directory (persists across app updates)."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "MusicTranscriber"
    if system == "Windows":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "MusicTranscriber"
    # Linux / other POSIX
    xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(xdg) / "MusicTranscriber"


def get_venv_python(data_dir: Path) -> Path:
    if platform.system() == "Windows":
        return data_dir / "venv" / "Scripts" / "python.exe"
    return data_dir / "venv" / "bin" / "python3"


def find_bundled_python(resources: Path) -> Path:
    candidates = [
        resources / "python" / "bin" / "python3.12",
        resources / "python" / "bin" / "python3.11",
        resources / "python" / "bin" / "python3",
        resources / "python" / "python.exe",         # Windows
        resources / "python" / "Scripts" / "python.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise RuntimeError(
        f"Bundled Python not found in {resources / 'python'}.\n"
        "Re-run build_app.sh to rebuild the bundle."
    )


def get_ffmpeg_path(resources: Path) -> Path:
    name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    return resources / name


# ── First-run setup ──────────────────────────────────────────────────────────

def needs_setup(data_dir: Path) -> bool:
    venv_python = get_venv_python(data_dir)
    version_file = data_dir / ".requirements_version"
    if not venv_python.exists():
        return True
    if not version_file.exists():
        return True
    return version_file.read_text().strip() != REQUIREMENTS_VERSION


def run_setup(resources: Path, data_dir: Path) -> None:
    """Run setup_deps.py in a visible terminal so the user can see pip progress."""
    bundled_python = find_bundled_python(resources)
    setup_script = resources / "setup_deps.py"
    cmd_parts = [str(bundled_python), str(setup_script), str(data_dir), REQUIREMENTS_VERSION]

    system = platform.system()

    if system == "Darwin":
        shell_cmd = _shell_join(cmd_parts)
        applescript = (
            'tell application "Terminal" to activate\n'
            f'tell application "Terminal" to do script "{shell_cmd}"'
        )
        subprocess.run(["osascript", "-e", applescript], check=True)
        _wait_for_setup(data_dir)

    elif system == "Windows":
        shell_cmd = _shell_join(cmd_parts)
        # Start a new cmd window; keep it open after the script exits so the
        # user can read any error messages.
        subprocess.Popen(
            ["cmd", "/c", "start", "MusicTranscriber Setup", "cmd", "/k", shell_cmd],
            shell=False,
        )
        _wait_for_setup(data_dir)

    else:
        # Linux: try common terminal emulators in order of preference
        shell_cmd = _shell_join(cmd_parts) + '; echo; read -rp "Press Enter to close..."'
        terminals = [
            ["x-terminal-emulator", "-e", "bash", "-c"],
            ["gnome-terminal", "--", "bash", "-c"],
            ["xfce4-terminal", "-e"],
            ["konsole", "-e", "bash", "-c"],
            ["xterm", "-e", "bash", "-c"],
        ]
        launched = False
        for term_prefix in terminals:
            try:
                subprocess.Popen(term_prefix + [shell_cmd])
                launched = True
                break
            except FileNotFoundError:
                continue

        if launched:
            _wait_for_setup(data_dir)
        else:
            # No GUI terminal found — run inline (e.g. headless server)
            subprocess.run(cmd_parts, check=True)


def _shell_join(parts: list) -> str:
    """Join command parts into a properly-quoted shell string (handles spaces in paths)."""
    if platform.system() == "Windows":
        # cmd.exe quoting: wrap paths-with-spaces in double quotes
        result = []
        for p in parts:
            p = str(p)
            if " " in p or "\t" in p:
                p = '"' + p.replace('"', '""') + '"'
            result.append(p)
        return " ".join(result)
    return " ".join(shlex.quote(str(p)) for p in parts)


def _wait_for_setup(data_dir: Path, timeout_seconds: int = 7200) -> None:
    """Poll until setup_deps.py writes the expected version file."""
    version_file = data_dir / ".requirements_version"
    print("Waiting for setup to complete (this may take 10-30 min)...", flush=True)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if (
            version_file.exists()
            and version_file.read_text().strip() == REQUIREMENTS_VERSION
        ):
            print("Setup complete.", flush=True)
            return
        time.sleep(3)
    raise RuntimeError(
        "Setup did not complete within the expected time.\n"
        "Check the setup terminal window for errors."
    )


# ── Server lifecycle ─────────────────────────────────────────────────────────

def kill_existing_server() -> None:
    """Kill any process already bound to SERVER_PORT before starting a fresh one.

    Handles the case where the previous launcher crashed or was force-quit
    without the shutdown() handler running, leaving uvicorn still holding the port.
    """
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", SERVER_PORT)) != 0:
            return  # port is free, nothing to do

    system = platform.system()
    try:
        if system in ("Darwin", "Linux"):
            result = subprocess.run(
                ["lsof", "-ti", f":{SERVER_PORT}"],
                capture_output=True, text=True,
            )
            pids = [p for p in result.stdout.strip().split() if p.isdigit()]
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            if pids:
                time.sleep(1)  # give processes a moment to exit
        elif system == "Windows":
            subprocess.run(
                f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{SERVER_PORT}\') do taskkill /F /PID %a',
                shell=True, capture_output=True,
            )
    except Exception:
        pass  # best-effort; start_server will fail loudly if port is still taken


def _prewarm_ffmpeg(resources: Path) -> None:
    """Run ffmpeg once from the launcher process to trigger macOS first-run security checks
    before uvicorn starts, avoiding a timeout inside the async startup event."""
    ffmpeg = get_ffmpeg_path(resources)
    try:
        subprocess.run(
            [str(ffmpeg), "-version"],
            capture_output=True,
            timeout=60,
        )
    except Exception:
        pass  # validation is uvicorn's job; this is just a warm-up


def start_server(resources: Path, data_dir: Path) -> subprocess.Popen:
    venv_python = get_venv_python(data_dir)
    backend_dir = resources / "backend"
    web_dir = resources / "web"
    ffmpeg = get_ffmpeg_path(resources)

    env = os.environ.copy()
    env["MT_DATA_DIR"] = str(data_dir)
    env["MT_WEB_DIR"] = str(web_dir)

    # Chord model is small (12 MB) and bundled with the app — point directly at
    # it so the validator in config.py doesn't redirect it to the data dir.
    bundled_chord_model = resources / "backend" / "models" / "chord_detection" / "btc_model.pt"
    if bundled_chord_model.exists():
        env["CHORD_MODEL_PATH"] = str(bundled_chord_model)

    # Firebase service account, bundled at Resources/firebase-service-account.json —
    # enables publishing completed jobs to the hosted read-only viewer. The
    # packaged app has no .env file, so these are set directly here instead.
    bundled_firebase_creds = resources / "firebase-service-account.json"
    if bundled_firebase_creds.exists():
        env["FIREBASE_CREDENTIALS_PATH"] = str(bundled_firebase_creds)
        env["FIREBASE_STORAGE_BUCKET"] = "music-transcription-6702c.firebasestorage.app"

    # Prepend the bundled ffmpeg so the backend finds it regardless of what is
    # (or isn't) installed on the user's system.
    env["PATH"] = str(ffmpeg.parent) + os.pathsep + env.get("PATH", "")

    cmd = [
        str(venv_python), "-m", "uvicorn",
        "api.main:app",
        "--host", "127.0.0.1",
        "--port", str(SERVER_PORT),
        "--log-level", "warning",
    ]

    kwargs: dict = {"cwd": str(backend_dir), "env": env}
    if platform.system() == "Windows":
        # Prevent a console window from flashing open on Windows
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    return subprocess.Popen(cmd, **kwargs)


def wait_for_server(timeout_seconds: int = 30) -> bool:
    url = f"http://127.0.0.1:{SERVER_PORT}/health"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


# ── macOS dock icon + media permissions ──────────────────────────────────────

def _set_dock_icon(resources: Path) -> None:
    """Set the macOS dock/taskbar icon to the bundled .icns file."""
    try:
        from AppKit import NSApplication, NSImage
        icon_path = str(resources / "icon.icns")
        image = NSImage.alloc().initWithContentsOfFile_(icon_path)
        if image:
            NSApplication.sharedApplication().setApplicationIconImage_(image)
    except Exception:
        pass


def _register_media_permission_handler(window) -> None:
    """Register a WKWebView UIDelegate override on first page load.

    Called BEFORE webview.start() — hooks window.events.loaded so the override
    is installed after the BrowserView is fully initialized but before the user
    can interact with the Record tab.
    """
    def _on_loaded():
        try:
            from webview.platforms.cocoa import BrowserView
            import AppKit

            print(f"[mic] _on_loaded fired, window.uid={window.uid}", flush=True)
            print(f"[mic] BrowserView.instances keys: {list(BrowserView.instances.keys())}", flush=True)

            bv = BrowserView.instances.get(window.uid)
            if bv is None or not hasattr(bv, 'webview'):
                print(f"[mic] bv={bv}, has webview={hasattr(bv, 'webview') if bv else 'N/A'}", flush=True)
                return

            wkwebview = bv.webview
            original = wkwebview.UIDelegate()
            print(f"[mic] wkwebview={wkwebview}, original UIDelegate={original}", flush=True)

            class _MediaDelegate(AppKit.NSObject):
                def webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_(
                    self, wv, origin, frame, capture_type, handler
                ):
                    handler(1)  # WKPermissionDecisionGrant = 1

                def forwardingTargetForSelector_(self, sel):
                    if original is not None and original.respondsToSelector_(sel):
                        return original
                    return None

            delegate = _MediaDelegate.alloc().init()
            wkwebview.setUIDelegate_(delegate)
            bv._media_delegate = delegate  # strong reference to prevent GC
            print(f"[mic] UIDelegate override installed: {delegate}", flush=True)
        except Exception as e:
            import traceback
            print(f"[mic] setup FAILED: {e}", flush=True)
            traceback.print_exc()

    window.events.loaded += _on_loaded


# ── Webview helper ───────────────────────────────────────────────────────────

def _try_import_webview(data_dir: Path):
    """Import pywebview from the venv after setup has completed."""
    venv_site = (
        data_dir / "venv" / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    if venv_site.exists() and str(venv_site) not in sys.path:
        sys.path.insert(0, str(venv_site))
    try:
        import webview  # noqa: PLC0415
        return webview
    except Exception:
        return None


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    resources = get_resources()
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    if needs_setup(data_dir):
        print("First-time setup required — opening setup window...", flush=True)
        run_setup(resources, data_dir)

    print("Starting MusicTranscriber...", flush=True)
    _webview = _try_import_webview(data_dir)
    _prewarm_ffmpeg(resources)
    kill_existing_server()
    server = start_server(resources, data_dir)

    def shutdown(signum=None, frame=None):
        print("\nShutting down...", flush=True)
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Waiting for server on port {SERVER_PORT}...", flush=True)
    if not wait_for_server(timeout_seconds=120):
        print(
            "ERROR: Server did not start within 120 seconds.\n"
            f"Check {data_dir / 'logs' / 'api.log'} for details.",
            file=sys.stderr,
        )
        server.kill()
        sys.exit(1)

    url = f"http://127.0.0.1:{SERVER_PORT}"
    print(f"MusicTranscriber is running at {url}", flush=True)

    if _webview is not None:
        _webview.create_window(
            "Music Transcriber",
            url,
            width=1400,
            height=900,
            min_size=(800, 600),
        )
        win = _webview.windows[0]
        _register_media_permission_handler(win)
        _webview.start(func=lambda: _set_dock_icon(resources))
        shutdown()
    else:
        import webbrowser
        webbrowser.open(url)
        print("Close this window or press Ctrl+C to stop.", flush=True)
        server.wait()


if __name__ == "__main__":
    main()
