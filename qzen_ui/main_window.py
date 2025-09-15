# -*- coding: utf-8 -*-
"""
Qzen 主窗口模块。

定义了应用程序的主界面 MainWindow，包括所有控件的布局、信号与槽的连接。
主窗口负责接收用户输入，调用业务逻辑层的功能，并展示处理结果。
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QProgressBar,
)
from PyQt6.QtGui import QAction
import logging

# 定义本项目支持的文档文件类型
SUPPORTED_EXTENSIONS = {
    # 文本文档
    '.txt', '.md',
    # PDF 文档
    '.pdf',
    # Office 文档
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
}


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

        self._create_central_widget()
        self._create_menus()

    def _create_menus(self) -> None:
        """创建主菜单栏。"""
        menu_bar = self.menuBar()
        # --- 文件菜单 ---
        file_menu = menu_bar.addMenu("文件(&F)")

        db_config_action = QAction("数据库配置(&D)...", self)
        db_config_action.triggered.connect(self.show_db_config_dialog)
        file_menu.addAction(db_config_action)

    def _create_central_widget(self) -> None:
        """创建主窗口的中心控件布局。"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 路径配置区 ---
        path_layout = QGridLayout()
        self.source_dir_input = QLineEdit()
        self.source_dir_button = QPushButton("选择...")
        self.source_dir_button.clicked.connect(
            lambda: self._select_directory(self.source_dir_input, "选择源文件夹")
        )

        self.intermediate_dir_input = QLineEdit()
        self.intermediate_dir_button = QPushButton("选择...")
        self.intermediate_dir_button.clicked.connect(
            lambda: self._select_directory(self.intermediate_dir_input, "选择中间文件夹")
        )

        path_layout.addWidget(QLabel("源文件夹:"), 0, 0)
        path_layout.addWidget(self.source_dir_input, 0, 1)
        path_layout.addWidget(self.source_dir_button, 0, 2)
        path_layout.addWidget(QLabel("中间文件夹:"), 1, 0)
        path_layout.addWidget(self.intermediate_dir_input, 1, 1)
        path_layout.addWidget(self.intermediate_dir_button, 1, 2)

        main_layout.addLayout(path_layout)

        # --- 操作按钮和进度条 ---
        self.deduplicate_button = QPushButton("开始去重")
        self.deduplicate_button.clicked.connect(self.start_deduplication)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False) # 默认隐藏

        main_layout.addWidget(self.deduplicate_button)
        main_layout.addWidget(self.progress_bar)
        main_layout.addStretch() # 添加伸缩因子，让控件靠上

    def _select_directory(self, line_edit: QLineEdit, caption: str) -> None:
        """打开文件夹选择对话框并更新输入框。"""
        directory = QFileDialog.getExistingDirectory(self, caption)
        if directory:
            line_edit.setText(directory)

    def start_deduplication(self) -> None:
        """开始执行去重流程的入口方法。"""
        source_dir = self.source_dir_input.text()
        intermediate_dir = self.intermediate_dir_input.text()

        # --- 输入验证 ---
        if not self.db_handler:
            QMessageBox.warning(self, "警告", "请先配置并成功连接数据库！")
            return
        if not source_dir or not intermediate_dir:
            QMessageBox.warning(self, "警告", "请选择源文件夹和中间文件夹！")
            return

        # --- 准备并启动后台任务 ---
        from qzen_core.orchestrator import Orchestrator
        from qzen_ui.worker import Worker

        self.deduplicate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        orchestrator = Orchestrator(self.db_handler)
        self.worker = Worker(
            orchestrator.run_deduplication,
            source_path=source_dir,
            intermediate_path=intermediate_dir,
            allowed_extensions=SUPPORTED_EXTENSIONS,
            progress_callback=self.update_progress
        )
        self.worker.result_ready.connect(self.on_task_finished)
        self.worker.error_occurred.connect(self.on_task_error)
        self.worker.start()

    def update_progress(self, current_value: int, max_value: int, status_text: str) -> None:
        """更新进度条和状态的回调函数。"""
        self.progress_bar.setMaximum(max_value)
        self.progress_bar.setValue(current_value)
        self.setWindowTitle(f"Qzen (千针) - {status_text}")

    def on_task_finished(self) -> None:
        """处理任务正常完成的回调。"""
        self.deduplicate_button.setEnabled(True)
        self.setWindowTitle("Qzen (千针) - 本地文档智能整理")
        QMessageBox.information(self, "完成", "去重任务已成功完成！")

    def on_task_error(self, error: Exception) -> None:
        """处理任务发生异常的回调。"""
        logging.error(f"去重任务线程发生异常: {error}", exc_info=True)
        self.deduplicate_button.setEnabled(True)
        self.setWindowTitle("Qzen (千针) - 本地文档智能整理")
        QMessageBox.critical(self, "错误", f"任务执行失败！\n错误信息: {error}")

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