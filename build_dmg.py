#!/usr/bin/env python3
"""Build a DMG installer for Nobody Took Notes."""

import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    root = Path(__file__).parent
    app_path = root / "dist" / "Nobody Took Notes.app"
    dmg_path = root / "dist" / "Nobody Took Notes.dmg"

    print("Building DMG installer")
    print("=" * 40)
    print()

    if not app_path.exists():
        print("✗ App bundle not found. Run build.py first.")
        sys.exit(1)

    print(f"✓ Found app: {app_path}")

    # Remove old DMG if exists
    if dmg_path.exists():
        dmg_path.unlink()
        print("  Removed old DMG")

    # Create DMG using hdiutil
    print()
    print("Creating DMG...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        staging = tmp / "dmg_staging"
        staging.mkdir()

        # Copy app to staging
        subprocess.run([
            "cp", "-R", str(app_path), str(staging / "Nobody Took Notes.app")
        ], check=True)

        # Create Applications symlink for drag-and-drop
        (staging / "Applications").symlink_to("/Applications")

        # Create background instructions file
        readme = staging / "README.txt"
        readme.write_text(
            "Nobody Took Notes\n"
            "=================\n\n"
            "INSTALLATION:\n"
            "1. Drag 'Nobody Took Notes' to the Applications folder\n\n"
            "FIRST RUN (Important!):\n"
            "Because this app is not signed with an Apple Developer certificate,\n"
            "macOS will block it by default. To open it:\n\n"
            "Option A - Right-click method:\n"
            "  1. Right-click (or Control-click) the app in Applications\n"
            "  2. Choose 'Open' from the menu\n"
            "  3. Click 'Open' in the dialog that appears\n\n"
            "Option B - Terminal method (if Option A doesn't work):\n"
            "  Run this command in Terminal:\n"
            "  xattr -cr /Applications/Nobody\\ Took\\ Notes.app\n\n"
            "PERMISSIONS:\n"
            "- Grant microphone permission when prompted\n"
            "- Grant Screen Recording permission in System Settings for system audio\n\n"
            "REQUIREMENTS:\n"
            "- macOS 14.2+ (for system audio capture)\n"
            "- ffmpeg (brew install ffmpeg) for audio export\n"
        )

        # Create DMG
        result = subprocess.run([
            "hdiutil", "create",
            "-volname", "Nobody Took Notes",
            "-srcfolder", str(staging),
            "-ov",  # overwrite
            "-format", "UDZO",  # compressed
            str(dmg_path),
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"✗ hdiutil failed: {result.stderr}")
            sys.exit(1)

    size_mb = dmg_path.stat().st_size / (1024 * 1024)
    print()
    print("-" * 40)
    print(f"✓ DMG created: {dmg_path}")
    print(f"  Size: {size_mb:.1f} MB")
    print()
    print("Distribution:")
    print("  1. Upload to GitHub Releases or your website")
    print("  2. Users download, open DMG, drag app to Applications")
    print()
    print("Note: Without code signing, users must right-click > Open on first launch.")
    print("To sign: Get Apple Developer account ($99/yr) and use codesign/notarytool.")


if __name__ == "__main__":
    main()
