#!/bin/bash
# packaging/macos/build.sh — Builds MusicTranscriber.app and MusicTranscriber.dmg
#
# Run this script from the repo root:
#   bash packaging/macos/build.sh
#
# Prerequisites (install once):
#   brew install create-dmg
#
# The script auto-detects the current machine architecture (arm64 / x86_64)
# and downloads the matching python-build-standalone and ffmpeg binaries.
# Run on Apple Silicon to produce an arm64 build; run on Intel for x86_64.
# GitHub Actions builds both (see .github/workflows/release.yml).

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
APP_NAME="MusicTranscriber"
APP_VERSION="1.0.0"
BUNDLE_ID="com.sarthak.musictranscriber"

# python-build-standalone release (update to latest when bumping Python)
# Find latest at: https://github.com/astral-sh/python-build-standalone/releases
PBS_VERSION="3.11.13"
PBS_DATE="20250702"

# FFmpeg static build (BtbN/FFmpeg-Builds, gpl-shared release)
FFMPEG_VERSION="7.1"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIEWER_DIR="$REPO_ROOT/../music-transcription-viewer/music_transcriber"
BUILD_DIR="$REPO_ROOT/packaging/_build/macos"
APP_DIR="$BUILD_DIR/$APP_NAME.app"
RESOURCES="$APP_DIR/Contents/Resources"
DMG_STAGING="$BUILD_DIR/dmg_staging"

ARCH="$(uname -m)"   # arm64 or x86_64

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "▶  $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

require() {
    command -v "$1" &>/dev/null || die "'$1' not found. $2"
}

_hdiutil_dmg() {
    # hdiutil refuses to read directly from certain source directories
    # ("Resource busy"). Staging to /tmp avoids the issue and also lets
    # us add the drag-to-Applications shortcut without polluting the .app dir.
    local staging
    staging="$(mktemp -d /tmp/mt_dmg_staging.XXXXXX)"
    cp -R "$APP_DIR" "$staging/"
    ln -s /Applications "$staging/Applications"
    hdiutil create \
        -volname "Music Transcriber" \
        -srcfolder "$staging" \
        -ov -format UDZO \
        -fs HFS+ \
        "$DMG_PATH"
    rm -rf "$staging"
}

# ── Preflight checks ─────────────────────────────────────────────────────────
log "Checking prerequisites..."
require flutter   "Install Flutter: https://docs.flutter.dev/get-started/install/macos"
require curl      ""
require hdiutil   ""  # built into macOS
# create-dmg is optional; we fall back to plain hdiutil if missing
CREATE_DMG="$(command -v create-dmg || true)"

# ── Step 1: Flutter web build ────────────────────────────────────────────────
log "Building Flutter web app..."
(
    cd "$VIEWER_DIR"
    flutter build web --release
)
FLUTTER_WEB_DIR="$VIEWER_DIR/build/web"
[ -d "$FLUTTER_WEB_DIR" ] || die "Flutter build output not found at $FLUTTER_WEB_DIR"

# ── Step 2: Download python-build-standalone ──────────────────────────────────
DOWNLOAD_CACHE="$REPO_ROOT/packaging/_cache"
mkdir -p "$DOWNLOAD_CACHE"

if [ "$ARCH" = "arm64" ]; then
    PBS_ARCH="aarch64-apple-darwin"
else
    PBS_ARCH="x86_64-apple-darwin"
fi

PBS_FILENAME="cpython-${PBS_VERSION}+${PBS_DATE}-${PBS_ARCH}-install_only_stripped.tar.gz"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_DATE}/${PBS_FILENAME}"
PBS_CACHE="$DOWNLOAD_CACHE/$PBS_FILENAME"

if [ ! -f "$PBS_CACHE" ]; then
    log "Downloading python-build-standalone ($ARCH)..."
    curl -L --progress-bar -o "$PBS_CACHE" "$PBS_URL"
else
    log "Using cached python-build-standalone."
fi

# ── Step 3: Download ffmpeg ───────────────────────────────────────────────────
if [ "$ARCH" = "arm64" ]; then
    FFMPEG_ARCH="arm64"
else
    FFMPEG_ARCH="64"
fi

# Using evermeet.cx for clean macOS static ffmpeg binaries
FFMPEG_CACHE="$DOWNLOAD_CACHE/ffmpeg-macos-${ARCH}"
if [ ! -f "$FFMPEG_CACHE" ]; then
    log "Downloading ffmpeg ($ARCH)..."
    FFMPEG_URL="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
    FFMPEG_ZIP="$DOWNLOAD_CACHE/ffmpeg-macos-${ARCH}.zip"
    curl -L --progress-bar -o "$FFMPEG_ZIP" "$FFMPEG_URL"
    unzip -o -j "$FFMPEG_ZIP" "ffmpeg" -d "$DOWNLOAD_CACHE"
    mv "$DOWNLOAD_CACHE/ffmpeg" "$FFMPEG_CACHE"
    chmod +x "$FFMPEG_CACHE"
else
    log "Using cached ffmpeg."
fi

# ── Step 4: Assemble .app bundle ──────────────────────────────────────────────
log "Assembling $APP_NAME.app..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$RESOURCES"

# Info.plist
cp "$REPO_ROOT/packaging/macos/Info.plist" "$APP_DIR/Contents/"

# App icon — must live in Resources/ and be referenced by CFBundleIconFile in Info.plist
cp "$REPO_ROOT/packaging/macos/icon.icns" "$RESOURCES/icon.icns"

# Firebase service account — enables publishing completed jobs to the hosted
# read-only viewer. Lives at the top level of Resources/ (not inside backend/,
# which excludes it) so launcher.py can point FIREBASE_CREDENTIALS_PATH at it
# directly without needing a bundled .env file.
if [ -f "$REPO_ROOT/firebase-service-account.json" ]; then
    cp "$REPO_ROOT/firebase-service-account.json" "$RESOURCES/firebase-service-account.json"
else
    log "  WARNING: firebase-service-account.json not found at repo root — publishing will be disabled in this build."
fi

# Executable (entrypoint shell script)
cp "$REPO_ROOT/packaging/macos/entrypoint.sh" "$APP_DIR/Contents/MacOS/$APP_NAME"
chmod +x "$APP_DIR/Contents/MacOS/$APP_NAME"

# Bundled Python
log "  Extracting Python..."
mkdir -p "$RESOURCES/python"
tar -xzf "$PBS_CACHE" -C "$RESOURCES/python" --strip-components=1

# Bundled ffmpeg — strip all xattrs so macOS doesn't scan it on first subprocess exec
cp "$FFMPEG_CACHE" "$RESOURCES/ffmpeg"
chmod +x "$RESOURCES/ffmpeg"
xattr -c "$RESOURCES/ffmpeg" 2>/dev/null || true

# Flutter web build
log "  Copying Flutter web build..."
cp -R "$FLUTTER_WEB_DIR" "$RESOURCES/web"

# Backend Python source (exclude secrets, caches, user data, large models)
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
cp "$REPO_ROOT/packaging/launcher.py"               "$RESOURCES/"
cp "$REPO_ROOT/packaging/setup_deps.py"             "$RESOURCES/"
cp "$REPO_ROOT/packaging/requirements-launcher.txt" "$RESOURCES/"

log "  Bundle assembled at $APP_DIR"

# ── Step 5: Create .dmg ───────────────────────────────────────────────────────
DMG_PATH="$BUILD_DIR/${APP_NAME}-${APP_VERSION}-macOS-${ARCH}.dmg"
rm -f "$DMG_PATH"

log "Creating DMG..."
if [ -n "$CREATE_DMG" ]; then
    create-dmg \
        --volname "$APP_NAME" \
        --volicon "$REPO_ROOT/packaging/macos/icon.icns" \
        --window-size 540 380 \
        --icon-size 128 \
        --icon "${APP_NAME}.app" 130 170 \
        --app-drop-link 400 170 \
        --hide-extension "${APP_NAME}.app" \
        "$DMG_PATH" \
        "$APP_DIR" \
    2>/dev/null || true  # create-dmg exits non-zero if no code signing; that's OK
    # Fallback to hdiutil if create-dmg failed (e.g. icon.icns missing)
    [ -f "$DMG_PATH" ] || _hdiutil_dmg
else
    _hdiutil_dmg
fi

log ""
log "✓ Build complete:"
log "  App bundle : $APP_DIR"
log "  DMG        : $DMG_PATH"
log ""
log "To distribute: share the .dmg file."
log "Users must right-click → Open on first launch (Gatekeeper bypass)."
log "For seamless double-click: sign and notarize with an Apple Developer account."
