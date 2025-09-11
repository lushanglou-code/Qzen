# -*- coding: utf-8 -*-
"""
Qzen (千针) 应用程序主入口。

该文件负责初始化Qt应用程序、创建并显示主窗口，是整个程序的起点。
"""

import sys
import logging

from PyQt6.QtWidgets import QApplication

from qzen_ui.main_window import MainWindow
from qzen_utils.logger_config import setup_logging


def main() -> None:
    """应用程序主函数。"""
    # --- 根据官方文档手动注册 SQLAlchemy 方言 ---
    # 解决 "Can't load plugin: sqlalchemy.dialects:dm.dmpython" 的问题。
    # 这是因为 SQLAlchemy_dm 包可能未被 pip 正确识别其入口点。
    # 我们在此强制 SQLAlchemy 将 'dm' 和 'dm.dmpython' 别名
    # 映射到 sqlalchemy_dm 包的方言实现上。
    try:
        from sqlalchemy.dialects import registry
        registry.register("dm", "sqlalchemy_dm.dmPython", "DMDialect_dmPython")
        registry.register("dm.dmPython", "sqlalchemy_dm.dmPython", "DMDialect_dmPython")
    except ImportError:
        # 如果 SQLAlchemy_dm 未安装，这里会失败。
        logging.critical("方言包 'SQLAlchemy_dm' 未安装，无法注册数据库方言。")
    except Exception as e:
        logging.error(f"手动注册DM8方言时发生未知错误: {e}")

    # 在程序最开始就设置好日志系统
    setup_logging()
    logging.info("Qzen 应用程序启动...")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
