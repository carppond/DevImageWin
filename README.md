# DevImageWin

[中文说明](README_CN.md)

A Windows GUI tool for iOS developers to enable Developer Mode and mount Developer Disk Image on USB-connected devices — no Xcode or macOS required.

## Features

- **Detect iOS Device** — Automatically detect USB-connected iPhone/iPad
- **Enable Developer Mode** — One-click enable with automatic device restart handling
- **Mount Developer Disk Image** — Bundled images for iOS 11.4–16.7; iOS 17+ via Apple TSS signing
- **Auto-install Apple Driver** — Bundled Apple Mobile Device Support, no need to install iTunes manually

## Download

Go to [Releases](../../releases) and download the latest `DevImageWin.exe`.

## Usage

1. Connect your iPhone/iPad via USB
2. Run `DevImageWin.exe`
3. Click **"检测设备"** (Detect Device)
4. If Developer Mode is off → Click **"开启开发者模式"** (Enable Developer Mode), wait for device to restart, unlock device, then click detect again
5. If DDI is not mounted → Click **"挂载磁盘映像"** (Mount Disk Image)

## Requirements

- Windows 10/11
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
Output: `dist/DevImageWin.exe`

## License

MIT
