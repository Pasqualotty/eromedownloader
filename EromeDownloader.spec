# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter
import cv2

ctk_path = os.path.dirname(customtkinter.__file__)
cv2_data_path = os.path.join(os.path.dirname(cv2.__file__), 'data')

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        (ctk_path, 'customtkinter'),
        (cv2_data_path, 'cv2/data'),
        ('src/assets/icon.ico', 'assets'),
    ],
    hiddenimports=[
        'customtkinter',
        'aiohttp',
        'aiofiles',
        'bs4',
        'PIL',
        'cv2',
        'brotli',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='EromeDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/assets/icon.ico',
)
