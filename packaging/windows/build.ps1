# packaging/windows/build.ps1 — Builds MusicTranscriber-Windows-x64-Setup.exe
#
# Run from the repo root in PowerShell (as Administrator recommended):
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
#
# Prerequisites (install once):
#   winget install Kitware.CMake           # not needed, just NSIS:
#   winget install NSIS.NSIS               # makensis must be on PATH
#   Flutter SDK on PATH (flutter build web)

$ErrorActionPreference = "Stop"

# ── Configuration ─────────────────────────────────────────────────────────────
$AppVersion   = "1.0.0"
$PythonVer    = "3.11.13"
$PBSDate      = "20250702"  # python-build-standalone release date

# ── Paths ─────────────────────────────────────────────────────────────────────
$RepoRoot    = (Get-Item "$PSScriptRoot\..\.." ).FullName
$ViewerDir   = (Get-Item "$RepoRoot\..\music-transcription-viewer\music_transcriber").FullName
$BuildDir    = "$RepoRoot\packaging\_build\windows"
$CacheDir    = "$RepoRoot\packaging\_cache"
$ResourcesDir = "$BuildDir\resources"

function Log($msg) { Write-Host "▶  $msg" -ForegroundColor Cyan }
function Die($msg) { Write-Error "ERROR: $msg"; exit 1 }

function Require($cmd) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Die "'$cmd' not found. Make sure it is on PATH."
    }
}

# ── Preflight ─────────────────────────────────────────────────────────────────
Log "Checking prerequisites..."
Require "flutter"
Require "makensis"
Require "curl"

# ── Step 1: Flutter web build ─────────────────────────────────────────────────
Log "Building Flutter web app..."
Push-Location $ViewerDir
flutter build web --release
Pop-Location

$FlutterWebDir = "$ViewerDir\build\web"
if (-not (Test-Path $FlutterWebDir)) { Die "Flutter build output not found at $FlutterWebDir" }

# ── Step 2: Download python-build-standalone (Windows x86_64) ─────────────────
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
$PBSFilename = "cpython-${PythonVer}+${PBSDate}-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
$PBSUrl      = "https://github.com/astral-sh/python-build-standalone/releases/download/${PBSDate}/${PBSFilename}"
$PBSCache    = "$CacheDir\$PBSFilename"

if (-not (Test-Path $PBSCache)) {
    Log "Downloading python-build-standalone (Windows x64)..."
    curl -L --progress-bar -o $PBSCache $PBSUrl
} else {
    Log "Using cached python-build-standalone."
}

# ── Step 3: Download ffmpeg (Windows x64 static) ──────────────────────────────
$FFmpegCache = "$CacheDir\ffmpeg-windows-x64.exe"
if (-not (Test-Path $FFmpegCache)) {
    Log "Downloading ffmpeg (Windows x64)..."
    # BtbN essentials-only static build (smallest, no external DLLs needed)
    $FFmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    $FFmpegZip = "$CacheDir\ffmpeg-win64.zip"
    curl -L --progress-bar -o $FFmpegZip $FFmpegUrl
    Expand-Archive -Force -Path $FFmpegZip -DestinationPath "$CacheDir\ffmpeg_tmp"
    $FFmpegBin = Get-ChildItem -Recurse "$CacheDir\ffmpeg_tmp" -Filter "ffmpeg.exe" | Select-Object -First 1
    Copy-Item $FFmpegBin.FullName $FFmpegCache
    Remove-Item -Recurse "$CacheDir\ffmpeg_tmp"
} else {
    Log "Using cached ffmpeg."
}

# ── Step 4: Assemble resources directory ──────────────────────────────────────
Log "Assembling resources..."
if (Test-Path $ResourcesDir) { Remove-Item -Recurse -Force $ResourcesDir }
New-Item -ItemType Directory -Force -Path $ResourcesDir | Out-Null

# Bundled Python
Log "  Extracting Python..."
New-Item -ItemType Directory -Force -Path "$ResourcesDir\python" | Out-Null
tar -xzf $PBSCache -C "$ResourcesDir\python" --strip-components=1

# Bundled ffmpeg
Copy-Item $FFmpegCache "$ResourcesDir\ffmpeg.exe"

# Flutter web build
Log "  Copying Flutter web build..."
Copy-Item -Recurse $FlutterWebDir "$ResourcesDir\web"

# Backend source (exclude secrets, caches, user data)
Log "  Copying backend source..."
$Excludes = @('.git','.env','*.env.*','firebase-service-account.json',
              '__pycache__','*.pyc','*.pyo','venv','storage','api.db*',
              'logs','packaging','models\separation','_build','_cache',
              '.serena','.localdev','.idea')

# Use robocopy for reliable multi-exclusion copy on Windows
$ExcludeDirs  = 'venv .venv storage logs output files packaging _build _cache .git .serena .localdev .idea .github'
$ExcludeFiles = '*.pyc *.pyo .env firebase-service-account.json logs.txt test_*.py temp_*.py'
robocopy $RepoRoot "$ResourcesDir\backend" /E /XD $ExcludeDirs /XF $ExcludeFiles | Out-Null

# Launcher + setup scripts
Copy-Item "$RepoRoot\packaging\launcher.py"    "$ResourcesDir\"
Copy-Item "$RepoRoot\packaging\setup_deps.py"  "$ResourcesDir\"

Log "Resources assembled at $ResourcesDir"

# ── Step 5: Run NSIS ──────────────────────────────────────────────────────────
Log "Building installer with NSIS..."
$NSIScript = "$PSScriptRoot\installer.nsi"
$OutputDir = $BuildDir

$IconPath = "$PSScriptRoot\icon.ico"

Push-Location $OutputDir
makensis /DRESOURCES_DIR="$ResourcesDir" /DAPP_VERSION="$AppVersion" /DICON_PATH="$IconPath" $NSIScript
Pop-Location

$InstallerPath = "$OutputDir\MusicTranscriber-${AppVersion}-Windows-x64-Setup.exe"
if (-not (Test-Path $InstallerPath)) {
    Die "NSIS did not produce the expected installer at $InstallerPath"
}

Log ""
Log "✓ Build complete:"
Log "  Installer: $InstallerPath"
Log ""
Log "Distribute the .exe — users double-click to install."
Log "Windows SmartScreen may warn on first run (expected for unsigned apps)."
Log "For seamless installs: sign the .exe with a code-signing certificate."
