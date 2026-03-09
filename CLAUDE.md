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

### CI Build
GitHub Actions (`.github/workflows/build.yml`) runs on `windows-latest`. DDI data is downloaded from a GitHub release tagged `ddi-data` (not via `prepare_ddi.py`). Triggered on push to `master`, `v*` tags, or `workflow_dispatch`. On tag push, creates a GitHub Release with the EXE.

### No Test Suite
There are no tests in this project.

## Architecture

Four-file architecture with clear separation:

- **`main.py`** — Entry point. Creates `QApplication`, shows `MainWindow`.
- **`ui.py`** — `MainWindow(QMainWindow)`. Fixed 480x420 window with three sections: Device Info, Developer Mode, DDI. Controls button state based on device state.
- **`workers.py`** — Three `QThread` subclasses (`DetectDeviceWorker`, `EnableDevModeWorker`, `MountDDIWorker`) that run blocking device operations off the GUI thread. Each emits `finished(dict)`, `error(str)`, and `progress(str)` signals.
- **`device_ops.py`** — All pymobiledevice3 logic: device detection, developer mode enablement, DDI mounting. Handles iOS 17+ (personalized DDI via `PersonalizedImageMounter`, requires internet for TSS) vs older iOS (bundled `DeveloperDiskImage.dmg`).

Supporting files:
- **`prepare_ddi.py`** — Pre-build utility that copies DDI files from the `developer_disk_image` pip package into `./ddi_data/`.
- **`build.spec`** — PyInstaller spec. Bundles `ddi_data/`, includes hidden imports for pymobiledevice3 submodules, outputs single-file EXE.

## Key Development Notes

- **DDI data is not in git** (`.gitignore` excludes `ddi_data/` and `ddi_data.zip`). Locally, run `prepare_ddi.py` after installing `developer-disk-image`. In CI, it's fetched from the `ddi-data` release.
- **Path resolution**: `device_ops._get_bundled_data_dir()` uses `sys._MEIPASS` when running from a frozen PyInstaller build, otherwise uses the script directory.
- **iOS 17+ DDI mount requires internet** at mount time for TSS personalization, even though base image files are bundled.
- **After enabling developer mode, the device reboots** — the `lockdown` object becomes invalid and the UI re-detects automatically.
- **UI text is in Chinese** — all labels, messages, and button text use Chinese strings.
- **IPython** is listed in CI deps but excluded from the PyInstaller build spec to avoid pulling in Jupyter dependencies.
