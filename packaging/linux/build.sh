#!/bin/bash
# packaging/linux/build.sh — Builds MusicTranscriber-x86_64.AppImage
#
# Run from the repo root on a Linux x86_64 machine:
#   bash packaging/linux/build.sh
#
# Prerequisites (install once):
#   sudo apt-get install curl rsync tar
#   Flutter SDK on PATH (flutter build web)
#   appimagetool is downloaded automatically if not on PATH.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
APP_VERSION="1.0.0"
PBS_VERSION="3.11.13"
PBS_DATE="20250702"

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIEWER_DIR="$REPO_ROOT/../music-transcription-viewer/music_transcriber"
BUILD_DIR="$REPO_ROOT/packaging/_build/linux"
CACHE_DIR="$REPO_ROOT/packaging/_cache"
APPDIR="$BUILD_DIR/AppDir"
RESOURCES="$APPDIR/resources"

ARCH="$(uname -m)"  # x86_64 or aarch64

log() { echo "▶  $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

require() { command -v "$1" &>/dev/null || die "'$1' not found. $2"; }

# ── Preflight ─────────────────────────────────────────────────────────────────
log "Checking prerequisites..."
require flutter "Install Flutter: https://docs.flutter.dev/get-started/install/linux"
require curl    ""
require rsync   "sudo apt-get install rsync"

# ── Step 1: Flutter web build ─────────────────────────────────────────────────
log "Building Flutter web app..."
(
    cd "$VIEWER_DIR"
    flutter build web --release
)
FLUTTER_WEB_DIR="$VIEWER_DIR/build/web"
[ -d "$FLUTTER_WEB_DIR" ] || die "Flutter build output not found at $FLUTTER_WEB_DIR"

# ── Step 2: Download python-build-standalone ──────────────────────────────────
mkdir -p "$CACHE_DIR"

if [ "$ARCH" = "aarch64" ]; then
    PBS_ARCH="aarch64-unknown-linux-gnu"
else
    PBS_ARCH="x86_64-unknown-linux-gnu"
fi

PBS_FILENAME="cpython-${PBS_VERSION}+${PBS_DATE}-${PBS_ARCH}-install_only_stripped.tar.gz"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_DATE}/${PBS_FILENAME}"
PBS_CACHE="$CACHE_DIR/$PBS_FILENAME"

if [ ! -f "$PBS_CACHE" ]; then
    log "Downloading python-build-standalone (Linux $ARCH)..."
    curl -L --progress-bar -o "$PBS_CACHE" "$PBS_URL"
else
    log "Using cached python-build-standalone."
fi

# ── Step 3: Download ffmpeg static binary ─────────────────────────────────────
FFMPEG_CACHE="$CACHE_DIR/ffmpeg-linux-${ARCH}"
if [ ! -f "$FFMPEG_CACHE" ]; then
    log "Downloading ffmpeg (Linux $ARCH static)..."
    if [ "$ARCH" = "aarch64" ]; then
        FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
    else
        FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    fi
    FFMPEG_TAR="$CACHE_DIR/ffmpeg-linux-${ARCH}.tar.xz"
    curl -L --progress-bar -o "$FFMPEG_TAR" "$FFMPEG_URL"
    FFMPEG_BIN=$(tar -tJf "$FFMPEG_TAR" | grep -E '^[^/]+/ffmpeg$' | head -1)
    tar -xJf "$FFMPEG_TAR" -C "$CACHE_DIR" "$FFMPEG_BIN"
    mv "$CACHE_DIR/$FFMPEG_BIN" "$FFMPEG_CACHE"
    chmod +x "$FFMPEG_CACHE"
else
    log "Using cached ffmpeg."
fi

# ── Step 4: Assemble AppDir ───────────────────────────────────────────────────
log "Assembling AppDir..."
rm -rf "$APPDIR"
mkdir -p "$RESOURCES"

# AppImage required files at root of AppDir
cp "$REPO_ROOT/packaging/linux/AppRun"                  "$APPDIR/"
cp "$REPO_ROOT/packaging/linux/MusicTranscriber.desktop" "$APPDIR/"
chmod +x "$APPDIR/AppRun"

# Icon (1024x1024 PNG preferred; fall back to a placeholder if not yet created)
if [ -f "$REPO_ROOT/packaging/linux/MusicTranscriber.png" ]; then
    cp "$REPO_ROOT/packaging/linux/MusicTranscriber.png" "$APPDIR/"
else
    log "  WARNING: No icon found at packaging/linux/MusicTranscriber.png"
    log "  AppImage will be built without an icon."
fi

# Bundled Python
log "  Extracting Python..."
mkdir -p "$RESOURCES/python"
tar -xzf "$PBS_CACHE" -C "$RESOURCES/python" --strip-components=1

# Bundled ffmpeg
cp "$FFMPEG_CACHE" "$RESOURCES/ffmpeg"
chmod +x "$RESOURCES/ffmpeg"

# Flutter web build
log "  Copying Flutter web build..."
cp -R "$FLUTTER_WEB_DIR" "$RESOURCES/web"

# Backend source (exclude secrets, caches, user data)
log "  Copying backend source..."
rsync -a \
    --exclude='.git' \
    --exclude='.env' \
    --exclude='*.env.*' \
    --exclude='firebase-service-account.json' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='venv/' \
    --exclude='.venv/' \
    --exclude='storage/' \
    --exclude='api.db*' \
    --exclude='logs/' \
    --exclude='logs.txt' \
    --exclude='output/' \
    --exclude='files/' \
    --exclude='*.app/' \
    --exclude='packaging/' \
    --exclude='models/separation/' \
    --exclude='_build/' \
    --exclude='_cache/' \
    --exclude='.serena/' \
    --exclude='.localdev/' \
    --exclude='.idea/' \
    --exclude='.github/' \
    --exclude='test_*.py' \
    --exclude='temp_*.py' \
    "$REPO_ROOT/" "$RESOURCES/backend/"

# Launcher + setup scripts
cp "$REPO_ROOT/packaging/launcher.py"    "$RESOURCES/"
cp "$REPO_ROOT/packaging/setup_deps.py" "$RESOURCES/"

log "AppDir assembled at $APPDIR"

# ── Step 5: Download appimagetool if needed ───────────────────────────────────
APPIMAGETOOL="$(command -v appimagetool || true)"
if [ -z "$APPIMAGETOOL" ]; then
    log "Downloading appimagetool..."
    if [ "$ARCH" = "aarch64" ]; then
        AT_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-aarch64.AppImage"
    else
        AT_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    fi
    APPIMAGETOOL="$CACHE_DIR/appimagetool"
    curl -L --progress-bar -o "$APPIMAGETOOL" "$AT_URL"
    chmod +x "$APPIMAGETOOL"
fi

# ── Step 6: Build AppImage ────────────────────────────────────────────────────
APPIMAGE_PATH="$BUILD_DIR/MusicTranscriber-${APP_VERSION}-${ARCH}.AppImage"
log "Building AppImage..."
ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_PATH"

log ""
log "✓ Build complete:"
log "  AppImage: $APPIMAGE_PATH"
log ""
log "Distribute the .AppImage file — users chmod +x it and double-click."
log "No installation required. Self-contained single file."
