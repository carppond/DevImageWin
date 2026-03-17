# DevImageWin

[中文说明](README_CN.md)

A Windows GUI tool for iOS developers to enable Developer Mode and mount Developer Disk Image on USB-connected devices — no Xcode or macOS required.

## Features

- **Detect iOS Device** — Automatically detect USB-connected iPhone/iPad
- **Enable Developer Mode** — One-click enable with automatic device restart handling; supports devices with passcode (reveals toggle in Settings)
- **Mount Developer Disk Image** — Bundled images for iOS 11.4–16.7; iOS 17+ via Apple TSS signing
- **Auto-install Apple Driver** — Bundled Apple Mobile Device Support, no need to install iTunes manually
- **Auto-retry on USB disconnect** — Automatically retries mount operation if USB connection is interrupted

## Download

Go to [Releases](../../releases) and download the EXE matching your iOS version:

| File | iOS Version | Size |
|------|------------|------|
| `DevImageWin_iOS17+.exe` | iOS 17.0 and above | ~100MB |
| `DevImageWin_Legacy.exe` | iOS 11.4 – 16.7 | ~550MB |

> **Most users should download `DevImageWin_iOS17+.exe`** — it covers all modern iOS devices.

## Usage

1. Connect your iPhone/iPad via USB
2. Run the downloaded EXE
3. Click **"检测设备"** (Detect Device)
4. If Developer Mode is off → Click **"开启开发者模式"** (Enable Developer Mode), wait for device to restart, unlock device, then click detect again
5. If DDI is not mounted → Click **"挂载磁盘映像"** (Mount Disk Image)

## Requirements

- Windows 10/11 (64-bit)
- iOS device connected via USB
- Internet connection (iOS 17+ only, for Apple TSS signing)

> The app will auto-install Apple Mobile Device Support driver on first launch if not present. No need to install iTunes.

## Build from Source

### Prerequisites
- Python 3.10+
- pip

### Steps
```bat
pip install pyinstaller pymobiledevice3 PySide6 developer-disk-image IPython pyimg4 ipsw_parser
python prepare_ddi.py
python -m PyInstaller build.spec --clean --noconfirm
```

Build specific version using environment variable:
```bat
set BUILD_TARGET=ios17plus
python -m PyInstaller build.spec --clean --noconfirm

set BUILD_TARGET=legacy
python -m PyInstaller build.spec --clean --noconfirm
```

| BUILD_TARGET | Output | Includes |
|-------------|--------|----------|
| `ios17plus` | `DevImageWin_iOS17+.exe` | Personalized DDI only |
| `legacy` | `DevImageWin_Legacy.exe` | DeveloperDiskImages only |
| _(default)_ | `DevImageWin.exe` | All DDI data |

## License

MIT
