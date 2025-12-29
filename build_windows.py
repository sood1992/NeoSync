"""
Windows Build Script
====================

Creates a Windows installer for NeoSync using PyInstaller and NSIS.

Usage:
    python build_windows.py

Requirements:
    pip install pyinstaller
    NSIS installed (https://nsis.sourceforge.io/)
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Configuration
APP_NAME = "NeoSync"
APP_VERSION = "1.0.0"
COMPANY = "NeoFox"
MAIN_SCRIPT = "neosync/__main__.py"
ICON = "assets/icon.ico"

# Directories
ROOT_DIR = Path(__file__).parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
INSTALLER_DIR = ROOT_DIR / "installer"


def clean():
    """Clean previous build artifacts"""
    print("Cleaning previous builds...")
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)


def create_icon():
    """Create icon if it doesn't exist"""
    icon_path = ROOT_DIR / ICON
    if not icon_path.exists():
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        # Create a placeholder icon
        print("Note: No icon found. Build will use default icon.")
        return None
    return str(icon_path)


def build_exe():
    """Build executable with PyInstaller"""
    print("Building executable with PyInstaller...")

    icon = create_icon()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",  # No console window
        "--onedir",  # Create a directory with all files
        "--noconfirm",
        "--clean",
        # Add hidden imports
        "--hidden-import", "PyQt6.QtSvg",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "scipy.signal",
        "--hidden-import", "scipy.fft",
        "--hidden-import", "librosa",
        "--hidden-import", "soundfile",
        "--hidden-import", "cv2",
        # Collect data files
        "--collect-data", "librosa",
        # Main script
        MAIN_SCRIPT,
    ]

    if icon:
        cmd.extend(["--icon", icon])

    subprocess.run(cmd, check=True, cwd=ROOT_DIR)
    print("Executable built successfully!")


def create_nsis_script():
    """Create NSIS installer script"""
    print("Creating NSIS installer script...")

    nsis_script = f'''
; NeoSync Installer Script
; ========================

!include "MUI2.nsh"

; General
Name "{APP_NAME}"
OutFile "{INSTALLER_DIR}/{APP_NAME}-{APP_VERSION}-Setup.exe"
InstallDir "$PROGRAMFILES64\\{COMPANY}\\{APP_NAME}"
InstallDirRegKey HKLM "Software\\{COMPANY}\\{APP_NAME}" "InstallDir"
RequestExecutionLevel admin

; Interface
!define MUI_ABORTWARNING
!define MUI_ICON "assets\\icon.ico"
!define MUI_UNICON "assets\\icon.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"

; Installer Section
Section "Install"
    SetOutPath "$INSTDIR"

    ; Copy all files from dist
    File /r "dist\\{APP_NAME}\\*.*"

    ; Create start menu shortcut
    CreateDirectory "$SMPROGRAMS\\{COMPANY}"
    CreateShortcut "$SMPROGRAMS\\{COMPANY}\\{APP_NAME}.lnk" "$INSTDIR\\{APP_NAME}.exe"

    ; Create desktop shortcut
    CreateShortcut "$DESKTOP\\{APP_NAME}.lnk" "$INSTDIR\\{APP_NAME}.exe"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\\Uninstall.exe"

    ; Write registry keys
    WriteRegStr HKLM "Software\\{COMPANY}\\{APP_NAME}" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" "DisplayName" "{APP_NAME}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" "UninstallString" "$INSTDIR\\Uninstall.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" "Publisher" "{COMPANY}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" "DisplayVersion" "{APP_VERSION}"
SectionEnd

; Uninstaller Section
Section "Uninstall"
    ; Remove files
    RMDir /r "$INSTDIR"

    ; Remove shortcuts
    Delete "$SMPROGRAMS\\{COMPANY}\\{APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\\{COMPANY}"
    Delete "$DESKTOP\\{APP_NAME}.lnk"

    ; Remove registry keys
    DeleteRegKey HKLM "Software\\{COMPANY}\\{APP_NAME}"
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}"
SectionEnd
'''

    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    script_path = INSTALLER_DIR / "installer.nsi"
    script_path.write_text(nsis_script)
    print(f"NSIS script created: {script_path}")
    return script_path


def build_installer(nsis_script):
    """Build installer with NSIS"""
    print("Building installer with NSIS...")

    # Find NSIS
    nsis_paths = [
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
        "makensis",
    ]

    makensis = None
    for path in nsis_paths:
        if os.path.exists(path) or shutil.which(path):
            makensis = path
            break

    if makensis is None:
        print("WARNING: NSIS not found. Skipping installer creation.")
        print("Download NSIS from: https://nsis.sourceforge.io/")
        return

    subprocess.run([makensis, str(nsis_script)], check=True)
    print(f"Installer created: {INSTALLER_DIR}/{APP_NAME}-{APP_VERSION}-Setup.exe")


def main():
    """Main build process"""
    print(f"Building {APP_NAME} v{APP_VERSION} for Windows")
    print("=" * 50)

    clean()
    build_exe()
    nsis_script = create_nsis_script()

    if sys.platform == "win32":
        build_installer(nsis_script)
    else:
        print("Note: Run on Windows to create NSIS installer")

    print()
    print("Build complete!")
    print(f"Executable: {DIST_DIR}/{APP_NAME}/{APP_NAME}.exe")


if __name__ == "__main__":
    main()
