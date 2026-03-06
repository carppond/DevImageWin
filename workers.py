from PySide6.QtCore import QThread, Signal

from device_ops import DeviceOpsError, detect_device, enable_dev_mode, mount_ddi


class DetectDeviceWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def run(self):
        self.progress.emit("正在检测设备...")
        try:
            result = detect_device()
            self.finished.emit(result)
        except DeviceOpsError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"未知错误：{e}")


class EnableDevModeWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, lockdown, parent=None):
        super().__init__(parent)
        self._lockdown = lockdown

    def run(self):
        self.progress.emit("正在开启开发者模式，设备将重启，请稍等...")
        try:
            msg = enable_dev_mode(self._lockdown)
            self.finished.emit({'message': msg})
        except DeviceOpsError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"未知错误：{e}")


class MountDDIWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, lockdown, parent=None):
        super().__init__(parent)
        self._lockdown = lockdown

    def run(self):
        self.progress.emit("正在挂载开发者磁盘映像...")
        try:
            msg = mount_ddi(self._lockdown)
            self.finished.emit({'message': msg})
        except DeviceOpsError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"未知错误：{e}")
