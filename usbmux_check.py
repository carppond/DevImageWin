import ctypes
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path

USBMUXD_HOST = "127.0.0.1"
USBMUXD_PORT = 27015


def _get_bundled_data_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def is_usbmuxd_available() -> bool:
    """检查 usbmuxd 服务是否可用（尝试连接 TCP 127.0.0.1:27015）"""
    if platform.system() != "Windows":
        return True
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((USBMUXD_HOST, USBMUXD_PORT))
        sock.close()
        return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


def try_start_apple_service() -> bool:
    """尝试启动 Apple Mobile Device Service"""
    if platform.system() != "Windows":
        return False
    try:
        subprocess.run(
            ["net", "start", "Apple Mobile Device Service"],
            capture_output=True, timeout=10,
        )
        return is_usbmuxd_available()
    except Exception:
        return False


def get_bundled_msi_path() -> Path | None:
    """获取内置的 AppleMobileDeviceSupport64.msi 路径"""
    msi = _get_bundled_data_dir() / "apple_driver" / "AppleMobileDeviceSupport64.msi"
    if msi.exists():
        return msi
    return None


def install_apple_driver() -> tuple[bool, str]:
    """
    安装内置的 Apple Mobile Device Support 驱动。
    需要管理员权限，会弹出 UAC 提示。
    返回 (success, message)。
    """
    msi = get_bundled_msi_path()
    if msi is None:
        return False, "未找到内置的 Apple 驱动安装包。"

    try:
        # 使用 ShellExecuteW 以管理员权限运行 msiexec
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            "msiexec.exe",
            f'/i "{msi}" /qn /norestart',
            None,
            0,  # SW_HIDE
        )
        # ShellExecuteW 返回值 > 32 表示成功启动
        if ret <= 32:
            return False, "安装被取消或权限不足。"

        # 等待安装完成（轮询 usbmuxd 端口）
        for _ in range(30):
            time.sleep(2)
            if is_usbmuxd_available():
                return True, "Apple 设备驱动安装成功！"

        # 安装可能成功但服务未启动，尝试启动
        if try_start_apple_service():
            return True, "Apple 设备驱动安装成功！"

        return False, "驱动已安装，但服务未启动。请重启电脑后重试。"

    except Exception as e:
        return False, f"安装失败：{e}"
