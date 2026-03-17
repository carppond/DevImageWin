# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevImageWin is a Windows-targeted PySide6 GUI tool ("iOS开发者设置工具") that helps iOS developers:
1. Detect a USB-connected iOS device
2. Enable Developer Mode on the device
3. Mount the Developer Disk Image (DDI)

Tech stack: Python 3.12, PySide6 (Qt6), pymobiledevice3, PyInstaller.

## Build Commands

### Local Build (Windows)
```bat
pip install pyinstaller pymobiledevice3 PySide6 developer-disk-image
python prepare_ddi.py                                    # copies DDI data from pip package into ./ddi_data/
python -m PyInstaller build.spec --clean --noconfirm     # output: dist/DevImageWin.exe
```
Or run `build.bat` which does all steps in sequence.

Build specific version via environment variable `BUILD_TARGET`:
```bat
set BUILD_TARGET=ios17plus
python -m PyInstaller build.spec --clean --noconfirm     # output: dist/DevImageWin_iOS17+.exe

set BUILD_TARGET=legacy
python -m PyInstaller build.spec --clean --noconfirm     # output: dist/DevImageWin_Legacy.exe
```

| BUILD_TARGET | Output EXE | DDI Data Included |
|-------------|-----------|-------------------|
| `ios17plus` | `DevImageWin_iOS17+.exe` (~100MB) | `PersonalizedImages/` only |
| `legacy` | `DevImageWin_Legacy.exe` (~550MB) | `DeveloperDiskImages/` only |
| _(default)_ | `DevImageWin.exe` (~600MB) | All DDI data |

### CI Build
GitHub Actions (`.github/workflows/build.yml`) runs on `windows-latest`. Triggered on `v*` tag push or `workflow_dispatch` (manual). Normal push to `master` does NOT trigger CI. CI builds **two EXEs** (`ios17plus` and `legacy`) in a single workflow run. On tag push, creates a GitHub Release with both EXEs.

CI does three extra things not needed locally:
1. Downloads `ddi_data.zip` from the GitHub release tagged `ddi-data` (downloaded once, each build target picks its subfolder)
2. Downloads iTunes installer from Apple, extracts `AppleMobileDeviceSupport64.msi` via 7-Zip, bundles it into `apple_driver/`
3. Installs `IPython`, `pyimg4`, `ipsw_parser` as additional dependencies

### Mac Testing
Use `test_devmode.py` to test the device operations directly on macOS without building the EXE:
```bash
python test_devmode.py
```

### No Test Suite
There are no automated tests in this project.

## Architecture

Six-file architecture:

- **`main.py`** — Entry point. Sets up file logging (`DevImageWin.log` next to EXE), creates `QApplication`, shows `MainWindow`.
- **`ui.py`** — `MainWindow(QMainWindow)`. Fixed 480×420 window with three sections: Device Info, Developer Mode, DDI. Controls button state based on device state. Checks for Apple driver on Windows before device detection.
- **`workers.py`** — Three `QThread` subclasses (`DetectDeviceWorker`, `EnableDevModeWorker`, `MountDDIWorker`) that call async device_ops functions via `asyncio.run()`. Each emits `finished(dict)`, `error(str)`, and `progress(str)` signals.
- **`device_ops.py`** — All pymobiledevice3 logic (async). Device detection, developer mode enablement, DDI mounting. Handles iOS 17+ (personalized DDI via `PersonalizedImageMounter`, requires internet for TSS) vs older iOS (bundled `DeveloperDiskImage.dmg`). Includes USB connection pre-verification and auto-retry on connection interruption.
- **`usbmux_check.py`** — Windows-specific: checks if usbmuxd service is available (TCP 127.0.0.1:27015), auto-installs bundled Apple Mobile Device Support MSI if missing.
- **`prepare_ddi.py`** — Pre-build utility that copies DDI files from the `developer_disk_image` pip package into `./ddi_data/`.

Supporting:
- **`build.spec`** — PyInstaller spec. Reads `BUILD_TARGET` env var to select DDI data and EXE name. Bundles `apple_driver/`, includes hidden imports for pymobiledevice3 submodules and metadata for `pyimg4`/`ipsw_parser`.
- **`build.bat`** — Windows one-click build script. Auto-detects Python (`py`/`python`/`python3`).
- **`test_devmode.py`** — Mac-only CLI script for testing the enable-developer-mode flow step by step with detailed output.

## Key Development Notes

- **All pymobiledevice3 APIs are async** in the version used. `device_ops.py` functions are `async def`, workers call them via `asyncio.run()`.
- **Windows hostname conflict (WinError 52)**: `create_using_usbmux()` must always pass `local_hostname='DevImageWin'` to avoid hostname resolution errors on Windows. This applies everywhere a lockdown connection is created, including reconnection after device restart.
- **Developer mode enable flow is manual**: Cannot use `enable_developer_mode(enable_post_restart=True)` because its internal `retry_create_using_usbmux()` doesn't pass `local_hostname`, causing WinError 52. Instead: send enable command → wait for device disconnect → poll for reconnect with custom hostname → send post-restart confirmation (with retry).
- **Passcode-set devices**: `enable_developer_mode()` raises `DeviceHasPasscodeSetError` when a passcode is set. Before attempting enable, `reveal_developer_mode_option_in_ui()` is called to make the Developer Mode toggle visible in Settings. The user is then guided to enable it manually.
- **Post-restart confirmation retries**: After device restart, `enable_developer_mode_post_restart()` may fail if services aren't fully ready. The code retries up to 3 times with increasing wait (5s/10s/15s), creating a fresh lockdown connection each time.
- **USB connection pre-verification**: Before `enable_dev_mode` and `mount_ddi`, `_verify_device_connection()` checks the device is still connected. Gives immediate feedback about USB cable issues instead of timing out.
- **mount_ddi auto-retry**: On connection interruption (`ConnectionAbortedError`, `BrokenPipeError`, etc.), `mount_ddi` retries up to 3 times with 3-second delays, creating a fresh lockdown connection each attempt.
- **Device reboots twice** when enabling developer mode. After `enable_developer_mode_post_restart()`, the device may restart again. The UI does NOT auto-detect after enable; it prompts the user to wait and manually click "检测设备".
- **Split EXE builds**: CI produces two EXEs via `BUILD_TARGET` env var. `device_ops.py` detects which DDI data is bundled and shows version-appropriate error messages (e.g., "please download Legacy version") when the wrong EXE is used for the device's iOS version.
- **DDI data is not in git** (`.gitignore` excludes `ddi_data/`, `ddi_data.zip`). Locally, run `prepare_ddi.py` after installing `developer-disk-image`. In CI, it's fetched from the `ddi-data` release.
- **Apple driver is bundled in EXE** (`apple_driver/AppleMobileDeviceSupport64.msi`, ~38MB). On Windows, if usbmuxd is not available, the app offers to silently install it with UAC elevation.
- **Path resolution**: `device_ops._get_bundled_data_dir()` uses `sys._MEIPASS` when running from a frozen PyInstaller build, otherwise uses the script directory.
- **iOS 17+ DDI mount requires internet** at mount time for TSS personalization. Network errors show a user-friendly message mentioning proxy/internet issues, with a retry button.
- **UI text is in Chinese** — all labels, messages, and button text use Chinese strings.
- **Logging**: `main.py` configures logging to both stdout and `DevImageWin.log` (in EXE directory). All device_ops functions log each step at INFO/DEBUG level for troubleshooting.
- **IPython** must be included in CI deps (not excluded from PyInstaller) — pymobiledevice3 imports it at runtime.
