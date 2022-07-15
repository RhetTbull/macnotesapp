# -*- mode: python ; coding: utf-8 -*-
# spec file for pyinstaller
# run `pyinstaller macnotesapp.spec`


import os
import importlib

pathex = os.getcwd()

from PyInstaller.utils.hooks import collect_data_files

# include necessary data files
datas = collect_data_files("macnotesapp")
datas.extend(
    [
        ("macnotesapp/macnotesapp.applescript", "macnotesapp"),
    ]
)

block_cipher = None

a = Analysis(
    ["cli.py"],
    pathex=[pathex],
    binaries=[],
    datas=datas,
    hiddenimports=["pkg_resources.py2_warn"],
    hookspath=[],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="notes",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
)
