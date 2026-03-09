import logging
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ui import MainWindow


def setup_logging():
    """配置日志，输出到 exe 同目录下的 DevImageWin.log"""
    if getattr(sys, 'frozen', False):
        log_dir = Path(sys.executable).parent
    else:
        log_dir = Path(__file__).parent

    log_file = log_dir / 'DevImageWin.log'

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8', mode='w'),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger().info(f"日志文件: {log_file}")


def main():
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("iOS开发者设置工具")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
