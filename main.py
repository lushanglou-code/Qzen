# -*- coding: utf-8 -*-
"""
Qzen (千针) 应用程序主入口 (v5.2 - MySQL 迁移最终版)。

此版本移除了所有与旧的 DM8 数据库方言注册相关的遗留代码，
完成了向 MySQL 技术栈的彻底迁移。
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
    1.  **设置日志系统**: 调用 `setup_logging` 来配置全局的日志记录器。
    2.  **启动Qt应用**: 初始化 `QApplication`，创建 `MainWindow` 实例，
        显示窗口，并启动事件循环。
    """
    # --- 步骤 1: 在程序最开始就设置好日志系统 ---
    setup_logging()
    logging.info("Qzen 应用程序启动...")

    # --- 步骤 2: 初始化并运行 Qt 应用程序 ---
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


# 当该脚本作为主程序直接执行时，调用 main() 函数。
if __name__ == '__main__':
    main()
