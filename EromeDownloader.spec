# -*- mode: python ; coding: utf-8 -*-
import os
import glob
import customtkinter
import cv2

ctk_path = os.path.dirname(customtkinter.__file__)
cv2_data_path = os.path.join(os.path.dirname(cv2.__file__), 'data')

# Collect all VC Runtime + Universal CRT DLLs
runtime_dlls = []
for dll in ['vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'ucrtbase.dll']:
    path = os.path.join('C:/Windows/System32', dll)
    if os.path.exists(path):
        runtime_dlls.append((path, '.'))

# UCRT api-ms-win-crt-* DLLs
for dll_path in glob.glob('C:/Windows/System32/downlevel/api-ms-win-crt-*.dll'):
    runtime_dlls.append((dll_path, '.'))

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=runtime_dlls,
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
