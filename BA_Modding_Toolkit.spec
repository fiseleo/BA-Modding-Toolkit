# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import get_package_paths

# 获取当前目录
current_dir = Path(os.path.abspath('.'))

# 获取UnityPy的安装路径
_, unitypy_path = get_package_paths('UnityPy')
# 定义UnityPy资源文件夹路径
unitypy_resources_path = Path(unitypy_path) / 'resources'

# 分析主脚本
a = Analysis(
    ['main.pyw'],
    pathex=[str(current_dir)],
    binaries=[],
    datas=[
        # 添加资源文件夹
        (str(current_dir / 'assets'), 'assets'),
        # 添加ui文件夹
        (str(current_dir / 'ui'), 'ui'),
        # 添加其他必要的Python文件
        (str(current_dir / 'utils.py'), '.'),
        (str(current_dir / 'processing.py'), '.'),
        (str(current_dir / 'maincli.py'), '.'),
        # 正确添加UnityPy的资源文件夹
        (str(unitypy_resources_path), 'UnityPy/resources')
    ],
    hiddenimports=[
        # 确保tkinterdnd2被正确包含
        'tkinterdnd2',
        'tkinterdnd2.tkdnd',
        # 确保Pillow的所有组件被包含
        'PIL._tkinter_finder',
        # 确保UnityPy被正确包含
        'UnityPy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# 创建PYZ文件
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 创建可执行文件
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BA Modding Toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 设置为False以隐藏控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 如果有图标文件，取消下面的注释并设置正确的路径
    # icon=str(current_dir / 'assets' / 'icon.ico'),
)