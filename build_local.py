#!/usr/bin/env python3
"""Local build script for testing builds on each platform.

Usage:
    python build_local.py [macos|windows|linux] [--release [patch|minor|major]]
"""
import argparse
import sys
import subprocess
import platform
import os
import re
import shutil
from pathlib import Path

from app.utils.versioning import bump_version, replace_project_version

ROOT = Path(__file__).parent
VERSION_FILE = ROOT / "app" / "version.py"
PYPROJECT_FILE = ROOT / "pyproject.toml"
INSTALLER_FILE = ROOT / "installer" / "JDP Presenter.iss"


def current_version() -> str:
    match = re.search(
        r'^APP_VERSION\s*=\s*"([^"]+)"',
        VERSION_FILE.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match is None:
        raise SystemExit("Could not read APP_VERSION from app/version.py")
    return match.group(1)


def increment_release_version(part: str) -> str:
    old_version = current_version()
    new_version = bump_version(old_version, part)

    version_text = VERSION_FILE.read_text(encoding="utf-8")
    VERSION_FILE.write_text(
        version_text.replace(
            f'APP_VERSION = "{old_version}"',
            f'APP_VERSION = "{new_version}"',
            1,
        ),
        encoding="utf-8",
    )
    pyproject_text = PYPROJECT_FILE.read_text(encoding="utf-8")
    PYPROJECT_FILE.write_text(
        replace_project_version(pyproject_text, new_version),
        encoding="utf-8",
    )
    installer_text = INSTALLER_FILE.read_text(encoding="utf-8")
    installer_text, count = re.subn(
        r'#define MyAppVersion "[^"]+"',
        f'#define MyAppVersion "{new_version}"',
        installer_text,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not update MyAppVersion in installer script")
    INSTALLER_FILE.write_text(installer_text, encoding="utf-8")
    print(f"Release version: {old_version} -> {new_version}")
    return new_version

def run(cmd, cwd=None):
    """Run a command and stream output."""
    print(f"→ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd or ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)

def build_macos():
    """Build macOS .app with PyInstaller (py2app has issues with modern setuptools)."""
    print("=== Building macOS .app with PyInstaller ===")
    run(".venv/bin/pip install -e '.[macos,build]'")
    run(
        ".venv/bin/pyinstaller --windowed --name \"JDP Presenter\" "
        "--specpath build "
        f"--icon \"{ROOT / 'assets' / 'icon.icns'}\" "
        f"--add-data \"{ROOT / 'assets'}:assets\" "
        f"--add-data \"{ROOT / 'app' / 'server' / 'templates'}:templates\" "
        f"--add-data \"{ROOT / 'app' / 'resources' / 'help'}:help\" "
        f"--add-data \"{ROOT / 'LICENSE'}:.\" "
        f"--add-data \"{ROOT / 'THIRD_PARTY_NOTICES.md'}:.\" "
        "--hidden-import=PySide6.QtMultimedia "
        "--hidden-import=PySide6.QtMultimediaWidgets "
        "--hidden-import=PySide6.QtNetwork "
        "--hidden-import=PySide6.QtWebSockets "
        "--hidden-import=sounddevice "
        "--hidden-import=numpy "
        "--hidden-import=qrcode "
        "--hidden-import=PIL "
        "--hidden-import=flask "
        "--hidden-import=flask_socketio "
        "--hidden-import=socketio "
        "--hidden-import=engineio.async_drivers.threading "
        f"\"{ROOT / 'app' / 'main.py'}\""
    )
    # Create DMG
    run('hdiutil create -volname "JDP Presenter" -srcfolder "dist/JDP Presenter.app" -ov -format UDZO "dist/JDP-Presenter-macos.dmg"')
    print("✅ macOS build complete: dist/JDP Presenter.app and dist/JDP-Presenter-macos.dmg")

def build_windows(version: str):
    """Build a self-contained Windows executable and Inno Setup installer."""
    print("=== Building Windows executable and installer ===")
    python = f'"{sys.executable}"'
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "PyInstaller is not installed in this environment. Install the project's build extra first."
        ) from exc
    (ROOT / "dist" / "JDP Presenter.exe").unlink(missing_ok=True)
    run(
        f"{python} -m PyInstaller --noconfirm --clean --windowed "
        "--specpath build "
        "--name \"JDP Presenter\" "
        f"--icon \"{ROOT / 'assets' / 'icon.ico'}\" "
        f"--add-data \"{ROOT / 'app' / 'server' / 'templates'};templates\" "
        f"--add-data \"{ROOT / 'app' / 'resources' / 'help'};help\" "
        f"--add-data \"{ROOT / 'LICENSE'};.\" "
        f"--add-data \"{ROOT / 'THIRD_PARTY_NOTICES.md'};.\" "
        "--hidden-import=PySide6.QtMultimedia "
        "--hidden-import=PySide6.QtMultimediaWidgets "
        "--hidden-import=PySide6.QtNetwork "
        "--hidden-import=PySide6.QtWebSockets "
        "--hidden-import=sounddevice "
        "--hidden-import=numpy "
        "--hidden-import=qrcode "
        "--hidden-import=PIL "
        "--hidden-import=flask "
        "--hidden-import=flask_socketio "
        "--hidden-import=socketio "
        "--hidden-import=engineio.async_drivers.threading "
        f"\"{ROOT / 'app' / 'main.py'}\""
    )
    iscc = _find_inno_compiler()
    if iscc is None:
        raise SystemExit(
            "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isdl.php"
        )
    run(f'"{iscc}" /DMyAppVersion={version} "installer/JDP Presenter.iss"')
    print("✅ Windows build complete: dist/JDP Presenter/JDP Presenter.exe")
    print("✅ Windows installer complete: dist/installer/JDP-Presenter-Setup.exe")


def _find_inno_compiler() -> Path | None:
    """Find ISCC in PATH or standard machine/per-user install locations."""
    on_path = shutil.which("ISCC.exe")
    if on_path:
        return Path(on_path)

    roots = (
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("PROGRAMFILES"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"),
    )
    for root in filter(None, roots):
        candidate = Path(root) / "Inno Setup 6" / "ISCC.exe"
        if candidate.exists():
            return candidate
    return None

def build_linux():
    """Build Linux AppImage with PyInstaller + linuxdeploy."""
    print("=== Building Linux AppImage ===")
    run("python -m pip install -e '.[build]'")
    run(
        "pyinstaller --windowed --name \"JDP Presenter\" "
        "--specpath build "
        f"--icon \"{ROOT / 'assets' / 'icon.png'}\" "
        f"--add-data \"{ROOT / 'assets'}:assets\" "
        f"--add-data \"{ROOT / 'app' / 'server' / 'templates'}:templates\" "
        f"--add-data \"{ROOT / 'app' / 'resources' / 'help'}:help\" "
        f"--add-data \"{ROOT / 'LICENSE'}:.\" "
        f"--add-data \"{ROOT / 'THIRD_PARTY_NOTICES.md'}:.\" "
        "--hidden-import=PySide6.QtMultimedia "
        "--hidden-import=PySide6.QtMultimediaWidgets "
        "--hidden-import=PySide6.QtNetwork "
        "--hidden-import=PySide6.QtWebSockets "
        "--hidden-import=sounddevice "
        "--hidden-import=numpy "
        "--hidden-import=qrcode "
        "--hidden-import=PIL "
        "--hidden-import=flask "
        "--hidden-import=flask_socketio "
        "--hidden-import=socketio "
        "--hidden-import=engineio.async_drivers.threading "
        f"\"{ROOT / 'app' / 'main.py'}\""
    )
    # Try to create AppImage if linuxdeploy is available
    if subprocess.run("which linuxdeploy", shell=True, capture_output=True).returncode == 0:
        run("linuxdeploy --appdir dist/JDP Presenter --output appimage")
        print("✅ Linux build complete: dist/JDP_Presenter-*.AppImage")
    else:
        print("✅ Linux build complete: dist/JDP Presenter/ (run ./JDP\\ Presenter to test)")
        print("   Install linuxdeploy to create AppImage: https://github.com/linuxdeploy/linuxdeploy")

def main():
    parser = argparse.ArgumentParser(description="Build JDP Presenter locally")
    parser.add_argument("target", nargs="?", choices=("macos", "darwin", "windows", "linux"))
    parser.add_argument(
        "--release",
        nargs="?",
        const="patch",
        choices=("patch", "minor", "major"),
        help="Increment the selected version component before building",
    )
    args = parser.parse_args()
    system = platform.system().lower()
    target = args.target or system
    version = increment_release_version(args.release) if args.release else current_version()
    print(f"Building JDP Presenter {version}")

    if target == "macos" or target == "darwin":
        if system != "darwin":
            print("⚠️  macOS build must run on macOS")
            sys.exit(1)
        build_macos()
    elif target == "windows":
        if system != "windows":
            print("⚠️  Windows build must run on Windows")
            sys.exit(1)
        build_windows(version)
    elif target == "linux":
        if system != "linux":
            print("⚠️  Linux build must run on Linux")
            sys.exit(1)
        build_linux()
    else:
        print(f"Unknown target: {target}")
        parser.error(f"Unknown target: {target}")

if __name__ == "__main__":
    main()