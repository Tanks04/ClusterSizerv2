# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller build spec for ClusterSizer. Bundles src/resources/ (fonts +
# QSS) as data files - without this, a frozen build launches completely
# unstyled with the OS default font, silently, since main.py's loaders
# fail soft (see main.py's _resource_root() for how paths are resolved
# both from source and from a frozen bundle).
#
# Build with:
#   pyinstaller ClusterSizer.spec
#
# See docs/BUILD.md for the full build/release procedure (venv setup,
# PySide6-Essentials swap, plugin pruning, packaging).

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('src/resources', 'src/resources')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test', 'pydoc', 'doctest'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ClusterSizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ClusterSizer',
)
