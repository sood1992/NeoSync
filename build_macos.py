"""
macOS Build Script
==================

Creates a macOS application bundle and DMG for NeoSync using py2app.

Usage:
    python build_macos.py

Requirements:
    pip install py2app dmgbuild
"""

import os
import sys
import shutil
import subprocess
import plistlib
from pathlib import Path

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


def create_icon():
    """Create icon if it doesn't exist"""
    icon_path = ROOT_DIR / ICON
    if not icon_path.exists():
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        print("Note: No icon found. Build will use default icon.")
        return None
    return str(icon_path)


def create_setup_py():
    """Create py2app setup script"""
    print("Creating py2app setup...")

    icon = create_icon()

    options = {
        'py2app': {
            'argv_emulation': False,
            'iconfile': icon,
            'plist': {
                'CFBundleName': APP_NAME,
                'CFBundleDisplayName': APP_NAME,
                'CFBundleIdentifier': BUNDLE_ID,
                'CFBundleVersion': APP_VERSION,
                'CFBundleShortVersionString': APP_VERSION,
                'NSHighResolutionCapable': True,
                'NSRequiresAquaSystemAppearance': False,  # Support dark mode
                'LSMinimumSystemVersion': '10.15',
                'NSHumanReadableCopyright': f'© 2024 {COMPANY}',
            },
            'includes': [
                'PyQt6.QtWidgets',
                'PyQt6.QtCore',
                'PyQt6.QtGui',
                'PyQt6.QtSvg',
                'scipy.signal',
                'scipy.fft',
                'librosa',
                'soundfile',
                'cv2',
                'numpy',
            ],
            'packages': [
                'neosync',
                'PyQt6',
                'scipy',
                'numpy',
                'librosa',
                'cv2',
            ],
            'frameworks': [],
        }
    }

    setup_content = f'''
from setuptools import setup

APP = ['{MAIN_SCRIPT}']
OPTIONS = {options}

setup(
    name='{APP_NAME}',
    app=APP,
    options=OPTIONS,
    setup_requires=['py2app'],
)
'''

    setup_path = ROOT_DIR / 'setup_macos.py'
    setup_path.write_text(setup_content)
    return setup_path


def build_app():
    """Build .app bundle with py2app"""
    print("Building .app bundle with py2app...")

    setup_py = create_setup_py()

    cmd = [
        sys.executable, str(setup_py),
        "py2app",
        "--dist-dir", str(DIST_DIR),
        "--bdist-base", str(BUILD_DIR),
    ]

    subprocess.run(cmd, check=True, cwd=ROOT_DIR)
    print("App bundle built successfully!")


def sign_app(app_path: Path, identity: str = None):
    """Code sign the application (requires Developer ID)"""
    print("Code signing application...")

    if identity is None:
        identity = os.environ.get('CODESIGN_IDENTITY', '-')

    if identity == '-':
        print("No signing identity found. Using ad-hoc signing.")
        print("For distribution, set CODESIGN_IDENTITY environment variable.")

    cmd = [
        'codesign',
        '--force',
        '--deep',
        '--sign', identity,
        '--options', 'runtime',
        '--entitlements', str(ROOT_DIR / 'entitlements.plist'),
        str(app_path),
    ]

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

    try:
        subprocess.run(cmd, check=True)
        print("Application signed successfully!")
    except subprocess.CalledProcessError:
        print("WARNING: Code signing failed. App may be blocked on other Macs.")


def create_dmg(app_path: Path):
    """Create DMG installer"""
    print("Creating DMG installer...")

    dmg_path = DIST_DIR / f"{APP_NAME}-{APP_VERSION}.dmg"

    # Try using dmgbuild
    try:
        import dmgbuild

        settings = {
            'filename': str(dmg_path),
            'volume_name': APP_NAME,
            'format': 'UDBZ',
            'size': None,
            'files': [str(app_path)],
            'symlinks': {'Applications': '/Applications'},
            'icon_locations': {
                f'{APP_NAME}.app': (140, 120),
                'Applications': (500, 120),
            },
            'background_color': '#1a1a1a',
            'window_rect': ((200, 120), (640, 400)),
            'icon_size': 128,
            'text_size': 14,
        }

        dmgbuild.build_dmg(str(dmg_path), APP_NAME, settings=settings)
        print(f"DMG created: {dmg_path}")
        return dmg_path

    except ImportError:
        print("dmgbuild not installed, using hdiutil...")

    # Fallback to hdiutil
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
    build_app()

    app_path = DIST_DIR / f"{APP_NAME}.app"

    if app_path.exists():
        sign_app(app_path)
        dmg_path = create_dmg(app_path)

        if os.environ.get('NOTARIZE', '').lower() == 'true':
            notarize_dmg(dmg_path)

    print()
    print("Build complete!")
    print(f"Application: {app_path}")
    print(f"DMG: {DIST_DIR}/{APP_NAME}-{APP_VERSION}.dmg")


if __name__ == "__main__":
    main()
