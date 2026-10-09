#!/usr/bin/env python3
"""Build Nobody Took Notes as a standalone macOS app."""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).parent

    print("Building Nobody Took Notes")
    print("=" * 40)
    print()

    # Check PyInstaller
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("✗ PyInstaller not found")
        print("  Install with: pip install pyinstaller")
        sys.exit(1)

    # Check nobodywho
    try:
        import nobodywho
        print(f"✓ nobodywho found at {Path(nobodywho.__file__).parent}")
    except ImportError:
        print("✗ nobodywho not found")
        sys.exit(1)

    print()
    print("Running PyInstaller...")
    print("-" * 40)

    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            str(root / "nobody.spec"),
        ],
        cwd=root,
    )

    if result.returncode != 0:
        print()
        print("Build failed!")
        sys.exit(1)

    print()
    print("-" * 40)
    print("Build complete!")
    print()

    app_path = root / "dist" / "Nobody Took Notes.app"
    if app_path.exists():
        print(f"App: {app_path}")
        print()
        print("To run:")
        print(f"  open '{app_path}'")
        print()
        print("To install:")
        print(f"  cp -r '{app_path}' /Applications/")
    else:
        print("Warning: App bundle not found at expected location")


if __name__ == "__main__":
    main()
