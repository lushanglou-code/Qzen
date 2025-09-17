# -*- coding: utf-8 -*-
"""
Qzen (千针) 应用程序主入口。

这是整个应用程序的起点。该文件负责执行所有必要的启动前初始化，
包括设置日志、注册数据库方言，然后创建并显示主窗口，最后进入
Qt 的应用程序事件循环。
"""

import sys
import logging

from PyQt6.QtWidgets import QApplication

from qzen_ui.main_window import MainWindow
from qzen_utils.logger_config import setup_logging


def main() -> None:
    """
    应用程序主函数，负责整个程序的初始化和启动流程。

    执行顺序如下：
    1.  **手动注册数据库方言**: 解决 `SQLAlchemy-DM` 包可能无法被
        SQLAlchemy 自动发现为入口点的问题。这是一个关键的兼容性补丁。
    2.  **设置日志系统**: 调用 `setup_logging` 来配置全局的日志记录器。
    3.  **启动Qt应用**: 初始化 `QApplication`，创建 `MainWindow` 实例，
        显示窗口，并启动事件循环。
    """
    # --- 步骤 1: 根据官方文档手动注册 SQLAlchemy 方言 ---
    # 这是一个关键的补丁，用于解决 "Can't load plugin: sqlalchemy.dialects:dm.dmpython" 的问题。
    # 这是因为 SQLAlchemy_dm 包可能未被 pip 正确识别其入口点。
    # 我们在此强制 SQLAlchemy 将 'dm' 和 'dm.dmpython' 别名
    # 映射到 sqlalchemy_dm 包的方言实现上。
    try:
        from sqlalchemy.dialects import registry
        registry.register("dm", "sqlalchemy_dm.dmPython", "DMDialect_dmPython")
        registry.register("dm.dmPython", "sqlalchemy_dm.dmPython", "DMDialect_dmPython")
    except ImportError:
        # 如果 SQLAlchemy_dm 未安装，这里会失败，记录严重错误。
        logging.critical("方言包 'SQLAlchemy_dm' 未安装，无法注册数据库方言。")
    except Exception as e:
        logging.error(f"手动注册DM8方言时发生未知错误: {e}")

    # --- 步骤 2: 在程序最开始就设置好日志系统 ---
    setup_logging()
    logging.info("Qzen 应用程序启动...")

    # --- 步骤 3: 初始化并运行 Qt 应用程序 ---
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


# 当该脚本作为主程序直接执行时，调用 main() 函数。
if __name__ == '__main__':
    main()
