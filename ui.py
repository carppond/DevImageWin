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

        self._lockdown = None
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

    # ---------- 检测设备 ----------

    def _on_detect_clicked(self):
        self._set_all_buttons_enabled(False)
        self._worker = DetectDeviceWorker(self)
        self._worker.finished.connect(self._on_device_detected)
        self._worker.error.connect(self._on_device_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_device_detected(self, result):
        self._lockdown = result['lockdown']

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
        if self._lockdown is None:
            return
        self._set_all_buttons_enabled(False)
        self._worker = EnableDevModeWorker(self._lockdown, self)
        self._worker.finished.connect(self._on_devmode_enabled)
        self._worker.error.connect(self._on_devmode_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_devmode_enabled(self, result):
        self.status_bar.showMessage(result.get('message', '开发者模式已开启'))
        QMessageBox.information(self, "成功", result.get('message', '开发者模式已开启'))
        # lockdown 对象在设备重启后已失效，需要重新检测
        self._lockdown = None
        self._on_detect_clicked()

    def _on_devmode_error(self, msg):
        self._update_buttons_by_state(False, False)
        self.status_bar.showMessage("开启开发者模式失败")
        QMessageBox.warning(self, "操作失败", msg)

    # ---------- 挂载 DDI ----------

    def _on_mount_ddi_clicked(self):
        if self._lockdown is None:
            return
        self._set_all_buttons_enabled(False)
        self._worker = MountDDIWorker(self._lockdown, self)
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
