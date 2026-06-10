# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Zipper System standalone installer.

Build via ``tools/build_installer.bat`` or directly:

    python -m PyInstaller tools/build_installer.spec --noconfirm --clean \
        --distpath installer

Produces ``installer/ZipperSystemInstaller.exe`` -- a single self-contained
binary (no Python needed on the target) that ships:

  * the tkinter installer GUI (installer_gui.py)
  * modules/ZipperSystem/  (plug-ins/ loader + icons/)
  * zipper_system/         (the pure-Python package -> installed into scripts/)
  * resources/module_template.mod

The installer lays these out into the user's Maya modules directory and writes
ZipperSystem.mod at runtime. Pure-Python plugin => one content set for all Maya
versions (no per-version .mll binaries to bundle).
"""

import os

block_cipher = None
HERE = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))


a = Analysis(
    [os.path.join(HERE, "installer_gui.py")],
    pathex=[HERE],
    binaries=[],
    datas=[
        # plug-ins/ loader + icons/ skeleton
        (os.path.join(HERE, "modules"), "modules"),
        # the package -- _package_src() resolves it at _MEIPASS/zipper_system
        (os.path.join(HERE, "zipper_system"), "zipper_system"),
        (os.path.join(HERE, "resources"), "resources"),
    ],
    hiddenimports=["installer_gui"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "numpy", "matplotlib", "pytest",
        "maya", "maya.cmds", "maya.api",
        "PySide2", "PySide6", "shiboken2", "shiboken6",
    ],
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
    name="ZipperSystemInstaller",
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
    icon=os.path.join(HERE, "modules", "ZipperSystem", "icons",
                      "ZipperSystem.png"),
)
