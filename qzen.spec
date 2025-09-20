# -*- mode: python ; coding: utf-8 -*-

# This is a PyInstaller spec file.

import os
import sysconfig
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# --- The definitive solution for packaging complex binary dependencies ---

# 1. Dynamically find the site-packages directory.
site_packages_path = sysconfig.get_paths()["purelib"]

# 2. Manually find and collect all necessary binary files (.dll, .pyd).
binaries = []

# Add the main dmPython pyd file, placing it in the root of the bundle.
dm_pyd_path = os.path.join(site_packages_path, 'dmPython.cp313-win_amd64.pyd')
if os.path.exists(dm_pyd_path):
    binaries.append((dm_pyd_path, '.'))
else:
    print(f"WARNING: dmPython.pyd not found at {dm_pyd_path}")

# Add all DLLs from the dpi folder, placing them in the root of the bundle.
dpi_path = os.path.join(site_packages_path, 'dpi')
if os.path.isdir(dpi_path):
    for filename in os.listdir(dpi_path):
        if filename.lower().endswith('.dll'):
            source_path = os.path.join(dpi_path, filename)
            binaries.append((source_path, '.')) # The '.' places them in the root.
else:
    print(f"WARNING: dpi directory not found at {dpi_path}")

# 3. Collect data files.
datas = []
datas += collect_data_files('sqlalchemy_dm')

# v3.2 修复: 明确添加 stopwords.txt 和 logo.ico
datas.append(('stopwords.txt', '.'))
datas.append(('logo.ico', '.'))

a = Analysis(
    ['main.py'],
    pathex=['D:\\workspace\\PythonProject'],
    binaries=binaries,  # Pass the collected binary files.
    datas=datas,        # Pass the collected data files.
    hiddenimports=[
        'PyQt6.sip',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._typedefs',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree',
        'sklearn.tree._utils',
        'sqlalchemy.sql.default_comparator',
        'scipy._lib.messagestream',
        'sqlalchemy_dm',
        'dmPython'
    ],
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
    [],
    exclude_binaries=True,
    name='Qzen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='logo.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Qzen'
)
