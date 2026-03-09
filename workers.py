import asyncio

from PySide6.QtCore import QThread, Signal

from device_ops import DeviceOpsError, detect_device, enable_dev_mode, mount_ddi


class DetectDeviceWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def run(self):
        self.progress.emit("正在检测设备...")
        try:
            result = asyncio.run(detect_device())
            self.finished.emit(result)
        except DeviceOpsError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"未知错误：{e}")


class EnableDevModeWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, udid, parent=None):
        super().__init__(parent)
        self._udid = udid

    def run(self):
        self.progress.emit("正在开启开发者模式，设备将重启，请稍等...")
        try:
            msg = asyncio.run(enable_dev_mode(self._udid))
            self.finished.emit({'message': msg})
        except DeviceOpsError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"未知错误：{e}")


class MountDDIWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, udid, parent=None):
        super().__init__(parent)
        self._udid = udid

    def run(self):
        self.progress.emit("正在挂载开发者磁盘映像...")
        try:
            msg = asyncio.run(mount_ddi(self._udid))
            self.finished.emit({'message': msg})
        except DeviceOpsError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"未知错误：{e}")
