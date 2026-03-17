# DevImageWin

[English](README.md)

Windows 端 iOS 开发者设置工具 —— 无需 Xcode 或 macOS，即可开启开发者模式并挂载开发者磁盘映像。

## 功能

- **检测 iOS 设备** — 自动识别 USB 连接的 iPhone/iPad
- **开启开发者模式** — 一键开启，自动处理设备重启；支持有锁屏密码的设备（自动显示设置中的开关）
- **挂载开发者磁盘映像** — 内置 iOS 11.4–16.7 镜像；iOS 17+ 通过 Apple TSS 在线签名
- **自动安装 Apple 驱动** — 内置 Apple Mobile Device Support，无需手动安装 iTunes
- **USB 断连自动重试** — 挂载过程中 USB 连接中断时自动重试

## 下载

前往 [Releases](../../releases) 下载对应 iOS 版本的 EXE：

| 文件 | iOS 版本 | 大小 |
|------|---------|------|
| `DevImageWin_iOS17+.exe` | iOS 17.0 及以上 | ~100MB |
| `DevImageWin_Legacy.exe` | iOS 11.4 – 16.7 | ~550MB |

> **大部分用户下载 `DevImageWin_iOS17+.exe` 即可** —— 覆盖所有现代 iOS 设备。

## 使用方法

1. 用 USB 连接 iPhone/iPad 到电脑
2. 运行下载的 EXE
3. 点击 **「检测设备」**
4. 如果开发者模式未开启 → 点击 **「开启开发者模式」**，等待手机重启并解锁后，再次点击检测设备
5. 如果磁盘映像未挂载 → 点击 **「挂载磁盘映像」**

## 系统要求

- Windows 10/11（64 位）
- iOS 设备通过 USB 连接
- 网络连接（仅 iOS 17+ 需要，用于 Apple TSS 签名）

> 首次使用时，程序会自动安装 Apple 设备驱动，无需手动安装 iTunes。

## 从源码构建

### 前置条件
- Python 3.10+
- pip

### 步骤
```bat
pip install pyinstaller pymobiledevice3 PySide6 developer-disk-image IPython pyimg4 ipsw_parser
python prepare_ddi.py
python -m PyInstaller build.spec --clean --noconfirm
```

通过环境变量构建指定版本：
```bat
set BUILD_TARGET=ios17plus
python -m PyInstaller build.spec --clean --noconfirm

set BUILD_TARGET=legacy
python -m PyInstaller build.spec --clean --noconfirm
```

| BUILD_TARGET | 输出 | 包含内容 |
|-------------|------|---------|
| `ios17plus` | `DevImageWin_iOS17+.exe` | 仅 Personalized DDI |
| `legacy` | `DevImageWin_Legacy.exe` | 仅 DeveloperDiskImages |
| _（默认）_ | `DevImageWin.exe` | 全部 DDI 数据 |

## 许可证

MIT
