"""
macOS Build Script
==================

Creates a macOS application bundle and DMG for NeoSync using PyInstaller.
(Switched from py2app to avoid recursion issues with complex dependencies)

Usage:
    python3 build_macos.py

Requirements:
    pip3 install pyinstaller
"""

import os
import sys
import shutil
import subprocess
import plistlib
from pathlib import Path

# Fix recursion limit for complex dependencies
sys.setrecursionlimit(5000)

# Configuration
APP_NAME = "NeoSync"
APP_VERSION = "1.0.0"
BUNDLE_ID = "com.neofox.neosync"
COMPANY = "NeoFox"
MAIN_SCRIPT = "neosync/__main__.py"
ICON = "assets/icon.icns"

# Directories
ROOT_DIR = Path(__file__).parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"


def clean():
    """Clean previous build artifacts"""
    print("Cleaning previous builds...")
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
    # Also clean spec file
    spec_file = ROOT_DIR / f"{APP_NAME}.spec"
    if spec_file.exists():
        spec_file.unlink()


def create_icon():
    """Create icon if it doesn't exist"""
    icon_path = ROOT_DIR / ICON
    if not icon_path.exists():
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        print("Note: No icon found. Build will use default icon.")
        return None
    return str(icon_path)


def build_app():
    """Build .app bundle with PyInstaller"""
    print("Building .app bundle with PyInstaller...")

    icon = create_icon()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",  # Creates .app bundle on macOS
        "--onedir",
        "--noconfirm",
        "--clean",
        # Hidden imports for PyQt6 and dependencies
        "--hidden-import", "PyQt6.QtSvg",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "scipy.signal",
        "--hidden-import", "scipy.fft",
        "--hidden-import", "scipy._lib.messagestream",
        "--hidden-import", "scipy.special._cdflib",
        "--hidden-import", "librosa",
        "--hidden-import", "librosa.util",
        "--hidden-import", "soundfile",
        "--hidden-import", "cv2",
        "--hidden-import", "numpy",
        "--hidden-import", "numpy.core._methods",
        "--hidden-import", "numpy.lib.format",
        # Collect all data files
        "--collect-data", "librosa",
        "--collect-submodules", "scipy",
        "--collect-submodules", "librosa",
        "--collect-submodules", "cv2",
        # macOS specific
        "--osx-bundle-identifier", BUNDLE_ID,
        # Output directory
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        # Main script
        MAIN_SCRIPT,
    ]

    if icon:
        cmd.extend(["--icon", icon])

    # Set environment
    env = os.environ.copy()
    env['PYTHONOPTIMIZE'] = '1'

    print("Running PyInstaller (this may take a few minutes)...")
    result = subprocess.run(cmd, cwd=ROOT_DIR, env=env)

    if result.returncode != 0:
        print("PyInstaller failed!")
        sys.exit(1)

    # Post-process: Update Info.plist
    app_path = DIST_DIR / f"{APP_NAME}.app"
    if app_path.exists():
        plist_path = app_path / "Contents" / "Info.plist"
        if plist_path.exists():
            with open(plist_path, 'rb') as f:
                plist = plistlib.load(f)

            plist.update({
                'CFBundleDisplayName': APP_NAME,
                'CFBundleVersion': APP_VERSION,
                'CFBundleShortVersionString': APP_VERSION,
                'NSHighResolutionCapable': True,
                'NSRequiresAquaSystemAppearance': False,  # Dark mode support
                'LSMinimumSystemVersion': '10.15',
                'NSHumanReadableCopyright': f'© 2024 {COMPANY}',
            })

            with open(plist_path, 'wb') as f:
                plistlib.dump(plist, f)

    print("App bundle built successfully!")
    return app_path


def sign_app(app_path: Path, identity: str = None):
    """Code sign the application (requires Developer ID)"""
    print("Code signing application...")

    if identity is None:
        identity = os.environ.get('CODESIGN_IDENTITY', '-')

    if identity == '-':
        print("No signing identity found. Using ad-hoc signing.")
        print("For distribution, set CODESIGN_IDENTITY environment variable.")

    # Create entitlements if not exist
    entitlements_path = ROOT_DIR / 'entitlements.plist'
    if not entitlements_path.exists():
        entitlements = {
            'com.apple.security.cs.allow-jit': True,
            'com.apple.security.cs.allow-unsigned-executable-memory': True,
            'com.apple.security.cs.disable-library-validation': True,
        }
        with open(entitlements_path, 'wb') as f:
            plistlib.dump(entitlements, f)

    cmd = [
        'codesign',
        '--force',
        '--deep',
        '--sign', identity,
        '--options', 'runtime',
        '--entitlements', str(entitlements_path),
        str(app_path),
    ]

    try:
        subprocess.run(cmd, check=True)
        print("Application signed successfully!")
    except subprocess.CalledProcessError:
        print("WARNING: Code signing failed. App may still work locally.")


def create_dmg(app_path: Path):
    """Create DMG installer"""
    print("Creating DMG installer...")

    dmg_path = DIST_DIR / f"{APP_NAME}-{APP_VERSION}.dmg"

    # Remove existing DMG
    if dmg_path.exists():
        dmg_path.unlink()

    # Use hdiutil (always available on macOS)
    temp_dmg = DIST_DIR / f"{APP_NAME}-temp.dmg"

    # Create temporary DMG
    subprocess.run([
        'hdiutil', 'create',
        '-volname', APP_NAME,
        '-srcfolder', str(app_path),
        '-ov', '-format', 'UDRW',
        str(temp_dmg)
    ], check=True)

    # Convert to compressed DMG
    subprocess.run([
        'hdiutil', 'convert', str(temp_dmg),
        '-format', 'UDZO',
        '-o', str(dmg_path)
    ], check=True)

    temp_dmg.unlink()
    print(f"DMG created: {dmg_path}")
    return dmg_path


def notarize_dmg(dmg_path: Path):
    """Notarize DMG with Apple (requires Apple Developer account)"""
    print("Notarizing DMG with Apple...")

    apple_id = os.environ.get('APPLE_ID')
    password = os.environ.get('APPLE_PASSWORD')
    team_id = os.environ.get('APPLE_TEAM_ID')

    if not all([apple_id, password, team_id]):
        print("Skipping notarization. Set APPLE_ID, APPLE_PASSWORD, APPLE_TEAM_ID.")
        return

    # Submit for notarization
    cmd = [
        'xcrun', 'notarytool', 'submit',
        str(dmg_path),
        '--apple-id', apple_id,
        '--password', password,
        '--team-id', team_id,
        '--wait'
    ]

    try:
        subprocess.run(cmd, check=True)
        print("Notarization successful!")

        # Staple the ticket
        subprocess.run([
            'xcrun', 'stapler', 'staple', str(dmg_path)
        ], check=True)
        print("Ticket stapled to DMG!")

    except subprocess.CalledProcessError as e:
        print(f"Notarization failed: {e}")


def main():
    """Main build process"""
    print(f"Building {APP_NAME} v{APP_VERSION} for macOS")
    print("=" * 50)

    if sys.platform != 'darwin':
        print("This script must be run on macOS")
        sys.exit(1)

    clean()
    app_path = build_app()

    if app_path and app_path.exists():
        sign_app(app_path)
        dmg_path = create_dmg(app_path)

        if os.environ.get('NOTARIZE', '').lower() == 'true':
            notarize_dmg(dmg_path)

        print()
        print("=" * 50)
        print("Build complete!")
        print(f"Application: {app_path}")
        print(f"DMG: {DIST_DIR}/{APP_NAME}-{APP_VERSION}.dmg")
    else:
        print("Build failed - app not created")
        sys.exit(1)


if __name__ == "__main__":
    main()
