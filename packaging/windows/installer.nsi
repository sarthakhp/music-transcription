; packaging/windows/installer.nsi — NSIS installer script for MusicTranscriber
; Compiled by build.ps1 via makensis.
;
; Produces: MusicTranscriber-<version>-Windows-x64-Setup.exe
; Install location: C:\Program Files\MusicTranscriber  (or user-chosen)

Unicode true

!define APP_NAME        "MusicTranscriber"
!define APP_VERSION     "1.0.0"
!define APP_PUBLISHER   "Sarthak"
!define APP_BUNDLE_ID   "com.sarthak.musictranscriber"
!define INSTALL_DIR     "$PROGRAMFILES64\${APP_NAME}"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
; RESOURCES_DIR is set on the makensis command line: /DRESOURCES_DIR=<path>

Name          "${APP_NAME} ${APP_VERSION}"
OutFile       "MusicTranscriber-${APP_VERSION}-Windows-x64-Setup.exe"
InstallDir    "${INSTALL_DIR}"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
ShowInstDetails show

; App icon for the installer window and installed shortcuts
; ICON_PATH is set on the makensis command line: /DICON_PATH=<path>
!ifdef ICON_PATH
  Icon "${ICON_PATH}"
  UninstallIcon "${ICON_PATH}"
!endif

; ── Pages ────────────────────────────────────────────────────────────────────
Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

; ── Install ───────────────────────────────────────────────────────────────────
Section "Install"
    SetOutPath "$INSTDIR\resources"
    File /r "${RESOURCES_DIR}\*"

    ; Uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Add/Remove Programs entry
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayName"     "${APP_NAME}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayVersion"  "${APP_VERSION}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "Publisher"       "${APP_PUBLISHER}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify"        1
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair"        1

    ; Copy icon so shortcuts can reference it from the install dir
    File /oname=$INSTDIR\icon.ico "${ICON_PATH}"

    ; Start Menu shortcut — use pythonw.exe so no console window flashes
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
        "$INSTDIR\resources\python\pythonw.exe" \
        '"$INSTDIR\resources\launcher.py"' \
        "$INSTDIR\icon.ico" 0

    ; Desktop shortcut
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
        "$INSTDIR\resources\python\pythonw.exe" \
        '"$INSTDIR\resources\launcher.py"' \
        "$INSTDIR\icon.ico" 0
SectionEnd

; ── Uninstall ─────────────────────────────────────────────────────────────────
Section "Uninstall"
    ; Remove installed files (but NOT user data in %APPDATA%)
    RMDir /r "$INSTDIR\resources"
    Delete "$INSTDIR\icon.ico"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir  "$INSTDIR"

    ; Remove shortcuts
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"

    ; Remove registry entries
    DeleteRegKey HKLM "${UNINSTALL_KEY}"

    MessageBox MB_OK \
        "$(^Name) has been uninstalled.$\n$\nYour personal data (models, job history) in %APPDATA%\MusicTranscriber was NOT removed. Delete that folder manually if you want to free up disk space."
SectionEnd
