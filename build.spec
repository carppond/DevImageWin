# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import copy_metadata

build_target = os.environ.get('BUILD_TARGET', 'all')

# 基础数据
base_datas = [
    ('apple_driver', 'apple_driver'),
    *copy_metadata('pyimg4'),
    *copy_metadata('ipsw_parser'),
]

# 根据构建目标选择 DDI 数据
if build_target == 'ios17plus':
    datas = base_datas + [('ddi_data/PersonalizedImages', 'ddi_data/PersonalizedImages')]
    exe_name = 'DevImageWin_iOS17+'
elif build_target == 'legacy':
    datas = base_datas + [('ddi_data/DeveloperDiskImages', 'ddi_data/DeveloperDiskImages')]
    exe_name = 'DevImageWin_Legacy'
else:
    datas = base_datas + [('ddi_data', 'ddi_data')]
    exe_name = 'DevImageWin'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'pyimg4',
        'ipsw_parser',
        'pymobiledevice3',
        'pymobiledevice3.lockdown',
        'pymobiledevice3.usbmux',
        'pymobiledevice3.services.amfi',
        'pymobiledevice3.services.mobile_image_mounter',
        'pymobiledevice3.services.heartbeat',
        'pymobiledevice3.services.lockdown_service',
        'pymobiledevice3.service_connection',
        'pymobiledevice3.pair_records',
        'pymobiledevice3.common',
        'pymobiledevice3.ca',
        'pymobiledevice3.irecv_devices',
        'pymobiledevice3.restore.tss',
        'pymobiledevice3.exceptions',
        'pymobiledevice3.lockdown_service_provider',
        'developer_disk_image',
        'developer_disk_image.repo',
        'packaging',
        'packaging.version',
        'zeroconf',
        'opack2',
        'construct',
        'asn1',
        'bpylist2',
        'cryptography',
        'srptools',
        'tqdm',
        'requests',
        'remotezip2',
        'ifaddr',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'uvicorn',
        'fastapi',
        'starlette',
        'matplotlib',
        'scipy',
        'pandas',
        'notebook',
        'jupyter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,
)
