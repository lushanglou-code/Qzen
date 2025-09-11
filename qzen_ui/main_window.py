# -*- coding: utf-8 -*-
"""
Qzen 主窗口模块。

定义了应用程序的主界面 MainWindow，包括所有控件的布局、信号与槽的连接。
主窗口负责接收用户输入，调用业务逻辑层的功能，并展示处理结果。
"""

from PyQt6.QtWidgets import QMainWindow, QMessageBox, QWidget
from PyQt6.QtGui import QAction
import logging


class MainWindow(QMainWindow):
    """
    应用程序主窗口。
    """
    def __init__(self, parent=None):
        """初始化主窗口界面和连接。"""
        super().__init__(parent)
        self.db_handler = None  # 移除类型提示，因为类是动态导入的
        self.worker = None # 用于持有工作线程的引用，防止被垃圾回收

        self.setWindowTitle("Qzen (千针) - 本地文档智能整理")
        self.setGeometry(100, 100, 800, 600)

        self._create_menus()

    def _create_menus(self) -> None:
        """创建主菜单栏。"""
        menu_bar = self.menuBar()
        # --- 文件菜单 ---
        file_menu = menu_bar.addMenu("文件(&F)")

        db_config_action = QAction("数据库配置(&D)...", self)
        db_config_action.triggered.connect(self.show_db_config_dialog)
        file_menu.addAction(db_config_action)

    def show_db_config_dialog(self) -> None:
        """显示数据库配置对话框并处理结果。"""
        # --- 延迟导入 ---
        # 将导入语句放在函数内部，确保只在需要时才加载这些模块，
        # 避免在程序启动时与Qt产生初始化冲突。
        from qzen_ui.config_dialog import ConfigDialog
        from qzen_ui.worker import Worker

        logging.info("打开数据库配置对话框...")
        dialog = ConfigDialog(self)
        if dialog.exec():  # 如果用户点击了 "OK"
            logging.info("数据库配置对话框被接受。")
            from qzen_data.database_handler import DatabaseHandler # 进一步延迟导入

            db_url = dialog.get_db_url()
            logging.debug(f"生成的数据库URL: {db_url}")

            # 实例化 DatabaseHandler，在调试时可以打开 echo=True
            logging.info("准备实例化 DatabaseHandler...")
            self.db_handler = DatabaseHandler(db_url, echo=False)
            logging.info("DatabaseHandler 实例化完毕。")

            # 测试数据库连接
            logging.info("准备测试数据库连接...")
            # 将 db_handler.test_connection 任务交给 Worker 线程执行
            self.worker = Worker(self.db_handler.test_connection)
            self.worker.result_ready.connect(self.on_db_test_success)
            self.worker.error_occurred.connect(self.on_db_test_error)
            self.worker.start() # 启动线程

    def on_db_test_success(self, result: bool) -> None:
        """处理数据库连接测试成功的回调。"""
        if result:
            logging.info("数据库连接成功。")
            QMessageBox.information(self, "成功", "数据库连接成功！")
        else:
            # test_connection 内部返回了 False
            logging.warning("数据库连接失败（内部逻辑）。")
            QMessageBox.critical(self, "错误", "无法连接到数据库！\n请检查配置信息是否正确。")
            self.db_handler = None  # 连接失败，重置handler
        self.worker = None # 释放线程引用

    def on_db_test_error(self, error: Exception) -> None:
        """处理数据库连接测试时发生异常的回调。"""
        logging.error(f"数据库连接测试线程异常: {error}", exc_info=True)
        QMessageBox.critical(self, "错误", f"数据库连接时发生未知错误！\n{error}")
        self.db_handler = None  # 连接失败，重置handler
        self.worker = None # 释放线程引用