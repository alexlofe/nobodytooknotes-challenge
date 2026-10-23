# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Nobody Took Notes macOS app."""

import sys
from pathlib import Path

block_cipher = None

# Find nobodywho native libraries
import nobodywho
nobodywho_path = Path(nobodywho.__file__).parent


# Collect nobodywho binaries
nobodywho_binaries = []
for ext in ['*.so', '*.dylib', '*.pyd']:
    for f in nobodywho_path.glob(ext):
        nobodywho_binaries.append((str(f), 'nobodywho'))

a = Analysis(
    ['nobody/__main__.py'],
    pathex=[],
    binaries=nobodywho_binaries,
    datas=[
        # Include UI files
        ('nobody/ui', 'nobody/ui'),
    ],
    hiddenimports=[
        'nobody',
        'nobody.capture',
        'nobody.capture.macos',
        'nobody.capture.mic',
        'nobody.stt',
        'nobody.summarise',
        'nobody.store',
        'nobody.server',
        'nobody.tray',
        'nobody.pipeline',
        'nobody.segment',
        'nobody.setup',
        'nobodywho',
        'catap',
        'sounddevice',
        'numpy',
        'fastapi',
        'uvicorn',
        'pystray',
        'pynput',
        'PIL',
        'PIL.Image',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='nobody',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window on macOS
    disable_windowed_traceback=False,
    argv_emulation=True,  # Handle file drops on macOS
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='nobody',
)

# macOS app bundle
app = BUNDLE(
    coll,
    name='Nobody Took Notes.app',
    icon=None,  # TODO: Add app icon
    bundle_identifier='ooo.nobodywho.nobodytooknotes',
    info_plist={
        'CFBundleName': 'Nobody Took Notes',
        'CFBundleDisplayName': 'Nobody Took Notes',
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleVersion': '1',
        'NSHighResolutionCapable': True,
        'LSBackgroundOnly': False,
        'LSUIElement': True,  # Menu bar app (no dock icon)
        # Privacy permissions
        'NSMicrophoneUsageDescription': 'Nobody Took Notes needs microphone access to record your voice during meetings.',
        'NSAppleEventsUsageDescription': 'Nobody Took Notes needs this permission to detect when you start or stop recording.',
        # Screen Recording is requested at runtime via catap
    },
)
