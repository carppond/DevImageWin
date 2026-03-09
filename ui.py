import platform

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from usbmux_check import (
    get_bundled_msi_path,
    install_apple_driver,
    is_usbmuxd_available,
    try_start_apple_service,
)
from workers import DetectDeviceWorker, EnableDevModeWorker, MountDDIWorker

# 状态指示器 HTML
STATUS_UNKNOWN = '<span style="color: gray;">\u25CF</span> 未知'
STATUS_ON = '<span style="color: green;">\u25CF</span> 已开启'
STATUS_OFF = '<span style="color: red;">\u25CF</span> 未开启'
STATUS_MOUNTED = '<span style="color: green;">\u25CF</span> 已挂载'
STATUS_NOT_MOUNTED = '<span style="color: red;">\u25CF</span> 未挂载'


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iOS 开发者设置工具")
        self.setFixedSize(480, 420)

        self._udid = None
        self._worker = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)

        # ---- 设备信息 ----
        device_group = QGroupBox("设备信息")
        device_layout = QVBoxLayout(device_group)

        info_pairs = [
            ("设备名称：", "lbl_name", "(未连接)"),
            ("iOS 版本：", "lbl_version", "--"),
            ("设备型号：", "lbl_model", "--"),
            ("UDID：", "lbl_udid", "--"),
        ]
        for label_text, attr, default in info_pairs:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(80)
            val = QLabel(default)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            setattr(self, attr, val)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            device_layout.addLayout(row)

        self.btn_detect = QPushButton("检测设备")
        self.btn_detect.clicked.connect(self._on_detect_clicked)
        device_layout.addWidget(self.btn_detect)
        layout.addWidget(device_group)

        # ---- 开发者模式 ----
        devmode_group = QGroupBox("开发者模式")
        devmode_layout = QVBoxLayout(devmode_group)

        self.lbl_devmode_status = QLabel(STATUS_UNKNOWN)
        self.lbl_devmode_status.setTextFormat(Qt.RichText)
        devmode_layout.addWidget(self.lbl_devmode_status)

        self.btn_enable_devmode = QPushButton("开启开发者模式")
        self.btn_enable_devmode.setEnabled(False)
        self.btn_enable_devmode.clicked.connect(self._on_enable_devmode_clicked)
        devmode_layout.addWidget(self.btn_enable_devmode)
        layout.addWidget(devmode_group)

        # ---- DDI ----
        ddi_group = QGroupBox("开发者磁盘映像 (DDI)")
        ddi_layout = QVBoxLayout(ddi_group)

        self.lbl_ddi_status = QLabel(STATUS_UNKNOWN)
        self.lbl_ddi_status.setTextFormat(Qt.RichText)
        ddi_layout.addWidget(self.lbl_ddi_status)

        self.btn_mount_ddi = QPushButton("挂载 DDI")
        self.btn_mount_ddi.setEnabled(False)
        self.btn_mount_ddi.clicked.connect(self._on_mount_ddi_clicked)
        ddi_layout.addWidget(self.btn_mount_ddi)
        layout.addWidget(ddi_group)

        layout.addStretch()

        # ---- 状态栏 ----
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    # ---------- 按钮禁用/启用 ----------

    def _set_all_buttons_enabled(self, enabled):
        self.btn_detect.setEnabled(enabled)
        self.btn_enable_devmode.setEnabled(enabled)
        self.btn_mount_ddi.setEnabled(enabled)

    def _update_buttons_by_state(self, dev_mode, ddi_mounted):
        self.btn_detect.setEnabled(True)
        self.btn_enable_devmode.setEnabled(not dev_mode)
        self.btn_mount_ddi.setEnabled(dev_mode and not ddi_mounted)

    # ---------- 驱动检测 ----------

    def _check_usbmuxd(self) -> bool:
        """检查 usbmuxd 服务，不可用时自动安装内置驱动"""
        if platform.system() != "Windows" or is_usbmuxd_available():
            return True

        self.status_bar.showMessage("正在尝试启动 Apple Mobile Device Service...")
        if try_start_apple_service():
            return True

        # 检查是否有内置驱动
        if get_bundled_msi_path() is None:
            QMessageBox.warning(
                self,
                "缺少 Apple 设备驱动",
                "未检测到 Apple Mobile Device Service，\n"
                "且程序内未包含驱动安装包。\n\n"
                "请手动安装 iTunes 或 Apple Devices 应用。",
            )
            return False

        reply = QMessageBox.question(
            self,
            "缺少 Apple 设备驱动",
            "未检测到 Apple 设备驱动，首次使用需要安装。\n\n"
            "点击「是」自动安装（需要管理员权限）。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return False

        self.btn_detect.setEnabled(False)
        self.status_bar.showMessage("正在安装 Apple 设备驱动，请在弹出的权限确认中点击「是」...")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        success, msg = install_apple_driver()
        if success:
            self.status_bar.showMessage(msg)
            QMessageBox.information(self, "安装成功", msg)
            return True
        else:
            self.btn_detect.setEnabled(True)
            self.status_bar.showMessage("驱动安装失败")
            QMessageBox.warning(self, "安装失败", msg)
            return False

    # ---------- 检测设备 ----------

    def _on_detect_clicked(self):
        if not self._check_usbmuxd():
            self.status_bar.showMessage("请先安装 Apple 设备驱动")
            return
        self._set_all_buttons_enabled(False)
        self._worker = DetectDeviceWorker(self)
        self._worker.finished.connect(self._on_device_detected)
        self._worker.error.connect(self._on_device_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_device_detected(self, result):
        self._udid = result['udid']

        self.lbl_name.setText(result['name'])
        self.lbl_version.setText(result['version'])
        self.lbl_model.setText(result['display_name'])
        self.lbl_udid.setText(result['udid'])

        dev_mode = result['dev_mode']
        ddi_mounted = result['ddi_mounted']

        self.lbl_devmode_status.setText(STATUS_ON if dev_mode else STATUS_OFF)
        self.lbl_ddi_status.setText(STATUS_MOUNTED if ddi_mounted else STATUS_NOT_MOUNTED)

        self._update_buttons_by_state(dev_mode, ddi_mounted)
        self.status_bar.showMessage("设备检测完成")

    def _on_device_error(self, msg):
        self.btn_detect.setEnabled(True)
        self.btn_enable_devmode.setEnabled(False)
        self.btn_mount_ddi.setEnabled(False)
        self.status_bar.showMessage("设备检测失败")
        QMessageBox.warning(self, "检测失败", msg)

    # ---------- 开启开发者模式 ----------

    def _on_enable_devmode_clicked(self):
        if self._udid is None:
            return
        self._set_all_buttons_enabled(False)
        self._worker = EnableDevModeWorker(self._udid, self)
        self._worker.finished.connect(self._on_devmode_enabled)
        self._worker.error.connect(self._on_devmode_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_devmode_enabled(self, result):
        self._udid = None
        self.btn_detect.setEnabled(True)
        self.btn_enable_devmode.setEnabled(False)
        self.btn_mount_ddi.setEnabled(False)
        self.status_bar.showMessage("开发者模式已开启，等待设备重启后请点击「检测设备」")
        QMessageBox.information(
            self, "成功",
            result.get('message', '开发者模式已开启。') + "\n\n"
            "设备可能会再次重启，请等待重启完成并解锁后，\n"
            "点击「检测设备」继续操作。"
        )

    def _on_devmode_error(self, msg):
        self._update_buttons_by_state(False, False)
        self.status_bar.showMessage("开启开发者模式失败")
        QMessageBox.warning(self, "操作失败", msg)

    # ---------- 挂载 DDI ----------

    def _on_mount_ddi_clicked(self):
        if self._udid is None:
            return
        self._set_all_buttons_enabled(False)
        self._worker = MountDDIWorker(self._udid, self)
        self._worker.finished.connect(self._on_ddi_mounted)
        self._worker.error.connect(self._on_ddi_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_ddi_mounted(self, result):
        self.lbl_ddi_status.setText(STATUS_MOUNTED)
        msg = result.get('message', 'DDI 挂载成功')
        self.status_bar.showMessage(msg)
        self._update_buttons_by_state(True, True)
        QMessageBox.information(self, "成功", msg)

    def _on_ddi_error(self, msg):
        self._update_buttons_by_state(True, False)
        self.status_bar.showMessage("DDI 挂载失败")
        QMessageBox.warning(self, "操作失败", msg)

    # ---------- 进度 ----------

    def _on_progress(self, msg):
        self.status_bar.showMessage(msg)
