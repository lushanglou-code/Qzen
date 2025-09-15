# -*- coding: utf-8 -*-
"""
Qzen 主窗口模块。

定义了应用程序的主界面 MainWindow，包括所有控件的布局、信号与槽的连接。
主窗口负责接收用户输入，调用业务逻辑层的功能，并展示处理结果。
"""

import os
import shutil
from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QProgressBar,
    QListWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDoubleSpinBox,
    QTabWidget,
)
from PyQt6.QtGui import QAction, QCloseEvent, QIcon
from PyQt6.QtCore import Qt, pyqtSignal
import logging

from qzen_data import file_handler
from qzen_utils import config_manager


SUPPORTED_EXTENSIONS = {
    # 文本文档
    '.txt', '.md',
    # PDF 文档
    '.pdf',
    # Office 文档
    '.doc', '.docx',
    '.xls', '.xlsx',
    '.ppt', '.pptx'
}


class MainWindow(QMainWindow):
    """
    应用程序主窗口。
    """
    progress_signal = pyqtSignal(int, int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_handler = None
        self.orchestrator = None
        self.worker = None
        self._is_vectorized = False

        self.setWindowTitle("Qzen (千针) - 本地文档智能整理")
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QIcon("logo.ico"))

        self._create_central_widget()
        self._create_menus()
        self._load_app_config()
        self._update_tab_states()

        self.progress_signal.connect(self.update_progress)

    def _create_menus(self) -> None:
        menu_bar = self.menuBar()
        help_menu = menu_bar.addMenu("帮助(&H)")
        about_action = QAction("关于 Qzen...", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_about_dialog(self):
        QMessageBox.about(
            self,
            "关于 Qzen (千针)",
            """<p><b>Qzen (千针) v1.0</b></p>
            <p>一个专为Windows用户设计的本地文档智能整理客户端。</p>
            <p>核心功能包括清理重复文件和对内容相似的文件进行聚类分析。</p>
            <br>
            <p><b>开发者:</b> Luzhao</p>
            <p><b>联系方式:</b> 597805263@qq.com</p>
            """
        )

    def _create_central_widget(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        setup_tab = QWidget()
        processing_tab = QWidget()
        analysis_tab = QWidget()
        organize_tab = QWidget()
        keyword_search_tab = QWidget()

        self.tabs.addTab(setup_tab, "1. 配置")
        self.tabs.addTab(processing_tab, "2. 批量处理")
        self.tabs.addTab(analysis_tab, "3. 交互式分析")
        self.tabs.addTab(organize_tab, "4. 自动整理")
        self.tabs.addTab(keyword_search_tab, "5. 关键词搜索")

        # --- 填充“配置”标签页 ---
        setup_layout = QVBoxLayout(setup_tab)
        self.db_config_button = QPushButton("第一步：配置数据库")
        self.db_config_button.clicked.connect(self.show_db_config_dialog)
        setup_layout.addWidget(self.db_config_button)

        path_layout = QGridLayout()
        self.source_dir_input = QLineEdit()
        self.source_dir_button = QPushButton("选择...")
        self.source_dir_button.clicked.connect(lambda: self._select_directory(self.source_dir_input, "选择源文件夹"))
        self.intermediate_dir_input = QLineEdit()
        self.intermediate_dir_button = QPushButton("选择...")
        self.intermediate_dir_button.clicked.connect(lambda: self._select_directory(self.intermediate_dir_input, "选择中间文件夹"))
        self.target_dir_input = QLineEdit()
        self.target_dir_button = QPushButton("选择...")
        self.target_dir_button.clicked.connect(lambda: self._select_directory(self.target_dir_input, "选择目标文件夹"))
        path_layout.addWidget(QLabel("第二步：源文件夹 (需要处理的原始文档): "), 0, 0)
        path_layout.addWidget(self.source_dir_input, 0, 1)
        path_layout.addWidget(self.source_dir_button, 0, 2)
        path_layout.addWidget(QLabel("第三步：中间文件夹 (存放去重后的唯一文档): "), 1, 0)
        path_layout.addWidget(self.intermediate_dir_input, 1, 1)
        path_layout.addWidget(self.intermediate_dir_button, 1, 2)
        path_layout.addWidget(QLabel("第四步：目标文件夹 (存放最终整理结果): "), 2, 0)
        path_layout.addWidget(self.target_dir_input, 2, 1)
        path_layout.addWidget(self.target_dir_button, 2, 2)
        setup_layout.addLayout(path_layout)
        setup_layout.addStretch()

        # --- 填充“批量处理”标签页 ---
        processing_layout = QVBoxLayout(processing_tab)
        self.deduplicate_button = QPushButton("执行去重 (将清空并覆盖中间文件夹和数据库)")
        self.vectorize_button = QPushButton("执行向量化")
        processing_layout.addWidget(self.deduplicate_button)
        processing_layout.addWidget(self.vectorize_button)
        processing_layout.addStretch()

        # --- 填充“交互式分析”标签页 ---
        analysis_layout = QHBoxLayout(analysis_tab)
        file_list_layout = QVBoxLayout()
        self.load_files_button = QPushButton("加载文件列表并预热引擎")
        self.file_list_widget = QListWidget()
        self.find_similar_button = QPushButton("查找相似文件")
        self.find_similar_button.setEnabled(False)
        file_list_layout.addWidget(self.load_files_button)
        file_list_layout.addWidget(self.file_list_widget)
        file_list_layout.addWidget(self.find_similar_button)
        results_layout = QVBoxLayout()
        results_layout.addWidget(QLabel("相似文件搜索结果:"))
        self.results_table_widget = QTableWidget()
        self.results_table_widget.setColumnCount(2)
        self.results_table_widget.setHorizontalHeaderLabels(["文件路径", "相似度"])
        self.results_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        results_layout.addWidget(self.results_table_widget)
        analysis_layout.addLayout(file_list_layout, 1)
        analysis_layout.addLayout(results_layout, 2)

        # --- 填充“自动整理”标签页 ---
        organize_layout = QVBoxLayout(organize_tab)
        cluster_controls_layout = QHBoxLayout()
        cluster_controls_layout.addWidget(QLabel("相似度阈值:"))
        self.similarity_threshold_spinbox = QDoubleSpinBox()
        self.similarity_threshold_spinbox.setRange(0.0, 1.0)
        self.similarity_threshold_spinbox.setSingleStep(0.05)
        self.similarity_threshold_spinbox.setValue(0.85)
        self.cluster_button = QPushButton("聚类并重命名")
        cluster_controls_layout.addWidget(self.similarity_threshold_spinbox)
        cluster_controls_layout.addWidget(self.cluster_button)
        cluster_controls_layout.addStretch()
        organize_layout.addLayout(cluster_controls_layout)
        organize_layout.addStretch()

        # --- 填充“关键词搜索”标签页 ---
        keyword_search_layout = QVBoxLayout(keyword_search_tab)
        keyword_input_layout = QHBoxLayout()
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("在此输入关键词...")
        keyword_input_layout.addWidget(QLabel("关键词:"))
        keyword_input_layout.addWidget(self.keyword_input)
        self.filename_search_button = QPushButton("按文件名搜索")
        self.content_search_button = QPushButton("按文件内容搜索")
        keyword_search_layout.addLayout(keyword_input_layout)
        keyword_search_layout.addWidget(self.filename_search_button)
        keyword_search_layout.addWidget(self.content_search_button)
        keyword_search_layout.addStretch()

        # --- 全局进度条 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # --- 连接信号 ---
        self.deduplicate_button.clicked.connect(self.start_deduplication)
        self.vectorize_button.clicked.connect(self.start_vectorization)
        self.load_files_button.clicked.connect(self.load_intermediate_files)
        self.file_list_widget.itemSelectionChanged.connect(self.update_button_states)
        self.find_similar_button.clicked.connect(self.on_find_similar_clicked)
        self.cluster_button.clicked.connect(self.start_clustering_and_renaming)
        self.filename_search_button.clicked.connect(self.start_filename_search)
        self.content_search_button.clicked.connect(self.start_content_search)

    def _update_tab_states(self):
        is_db_configured = self.orchestrator is not None
        is_vectorized = self._is_vectorized
        self.tabs.setTabEnabled(1, is_db_configured)
        self.tabs.setTabEnabled(2, is_vectorized)
        self.tabs.setTabEnabled(3, is_vectorized)
        self.tabs.setTabEnabled(4, is_db_configured)

    def _select_directory(self, line_edit: QLineEdit, caption: str):
        directory = QFileDialog.getExistingDirectory(self, caption)
        if directory:
            line_edit.setText(directory)

    def _load_app_config(self):
        config = config_manager.load_config()
        self.source_dir_input.setText(config.get("source_dir", ""))
        self.intermediate_dir_input.setText(config.get("intermediate_dir", ""))
        self.target_dir_input.setText(config.get("target_dir", ""))
        self.similarity_threshold_spinbox.setValue(config.get("similarity_threshold", 0.85))
        self.keyword_input.setText(config.get("last_keyword", ""))

    def _save_app_config(self):
        config = {
            "source_dir": self.source_dir_input.text(),
            "intermediate_dir": self.intermediate_dir_input.text(),
            "target_dir": self.target_dir_input.text(),
            "similarity_threshold": self.similarity_threshold_spinbox.value(),
            "last_keyword": self.keyword_input.text(),
        }
        config_manager.save_config(config)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_app_config()
        super().closeEvent(event)

    def update_button_states(self):
        self.find_similar_button.setEnabled(len(self.file_list_widget.selectedItems()) > 0)

    def _thread_safe_progress_callback(self, current: int, total: int, text: str):
        self.progress_signal.emit(current, total, text)

    def update_progress(self, current_value: int, max_value: int, status_text: str):
        self.progress_bar.setMaximum(max_value)
        self.progress_bar.setValue(current_value)
        self.setWindowTitle(f"Qzen (千针) - {status_text}")

    def on_task_finished(self, message: str):
        self.deduplicate_button.setEnabled(True)
        self.vectorize_button.setEnabled(True)
        self.cluster_button.setEnabled(True)
        self.filename_search_button.setEnabled(True)
        self.content_search_button.setEnabled(True)
        self.setWindowTitle("Qzen (千针) - 本地文档智能整理")
        QMessageBox.information(self, "完成", message)

    def on_vectorization_finished(self, message: str):
        self.on_task_finished(message)
        self._is_vectorized = True
        self._update_tab_states()

    def on_task_error(self, error: Exception):
        logging.error(f"后台任务线程发生异常: {error}", exc_info=True)
        self.deduplicate_button.setEnabled(True)
        self.vectorize_button.setEnabled(True)
        self.cluster_button.setEnabled(True)
        self.filename_search_button.setEnabled(True)
        self.content_search_button.setEnabled(True)
        self.setWindowTitle("Qzen (千针) - 本地文档智能整理")
        QMessageBox.critical(self, "错误", f"任务执行失败！\n错误信息: {error}")

    def show_db_config_dialog(self):
        from qzen_ui.config_dialog import ConfigDialog
        from qzen_data.database_handler import DatabaseHandler
        from qzen_core.orchestrator import Orchestrator
        dialog = ConfigDialog(self)
        if not dialog.exec():
            return

        db_url = dialog.get_db_url()
        self.db_handler = DatabaseHandler(db_url)
        self.orchestrator = Orchestrator(self.db_handler)

        try:
            logging.info("正在测试数据库连接...")
            if not self.db_handler.test_connection():
                raise ConnectionError("无法连接到数据库，请检查配置信息。")
            QMessageBox.information(self, "成功", "数据库连接成功！")
            self._update_tab_states()
        except Exception as e:
            logging.error(f"数据库初始化失败: {e}", exc_info=True)
            QMessageBox.critical(self, "数据库初始化失败", f"无法完成数据库的设置。\n请检查连接信息和数据库权限。\n\n错误: {e}")
            self.db_handler = None
            self.orchestrator = None
            self._update_tab_states()

    def start_deduplication(self):
        source_dir = self.source_dir_input.text()
        intermediate_dir = self.intermediate_dir_input.text()
        if not self.orchestrator or not source_dir or not intermediate_dir:
            QMessageBox.warning(self, "警告", "请先在“配置”标签页中成功配置数据库并选择源/中间文件夹！")
            return
        
        reply = QMessageBox.question(self, "确认操作", f"此操作将首先清空并重建数据库，并清空中间文件夹 '{intermediate_dir}'。\n\n您确定要开始一个全新的去重任务吗？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return

        try:
            # 在主线程中执行准备工作
            self.orchestrator.prepare_deduplication_workspace(intermediate_dir)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"准备工作空间失败！\n错误: {e}")
            return

        from qzen_ui.worker import Worker
        self.deduplicate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.worker = Worker(self.orchestrator.run_deduplication_core, source_path=source_dir, intermediate_path=intermediate_dir, allowed_extensions=SUPPORTED_EXTENSIONS, progress_callback=self._thread_safe_progress_callback)
        self.worker.result_ready.connect(lambda: self.on_task_finished("全新的去重任务已成功完成！"))
        self.worker.error_occurred.connect(self.on_task_error)
        self.worker.start()

    def start_vectorization(self):
        if not self.orchestrator:
            QMessageBox.warning(self, "警告", "请先在“配置”标签页中成功配置数据库！")
            return
        from qzen_ui.worker import Worker
        self.vectorize_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.worker = Worker(self.orchestrator.run_vectorization, progress_callback=self._thread_safe_progress_callback)
        self.worker.result_ready.connect(lambda: self.on_vectorization_finished("向量化任务已成功完成！"))
        self.worker.error_occurred.connect(self.on_task_error)
        self.worker.start()

    def load_intermediate_files(self):
        intermediate_dir = self.intermediate_dir_input.text()
        if not self.orchestrator or not intermediate_dir:
            QMessageBox.warning(self, "警告", "请先在“配置”标签页中成功配置数据库并选择中间文件夹！")
            return
        self.file_list_widget.clear()
        for file_path in file_handler.scan_files(intermediate_dir, SUPPORTED_EXTENSIONS):
            self.file_list_widget.addItem(file_path)
        from qzen_ui.worker import Worker
        self.worker = Worker(self.orchestrator.prime_similarity_engine)
        self.worker.result_ready.connect(lambda: self.on_task_finished("相似度引擎已预热完成！"))
        self.worker.error_occurred.connect(self.on_task_error)
        self.worker.start()

    def on_find_similar_clicked(self):
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items:
            return
        target_file_path = selected_items[0].text()
        from qzen_ui.worker import Worker
        self.find_similar_button.setEnabled(False)
        self.worker = Worker(self.orchestrator.find_top_n_similar_for_file, target_file_path=target_file_path, n=10)
        self.worker.result_ready.connect(self.on_search_complete)
        self.worker.error_occurred.connect(self.on_task_error)
        self.worker.start()

    def on_search_complete(self, results: list):
        self.results_table_widget.setRowCount(0)
        if not results:
            QMessageBox.information(self, "提示", "没有找到相似的文件。")
        else:
            self.results_table_widget.setRowCount(len(results))
            for row, (file_path, score) in enumerate(results):
                path_item = QTableWidgetItem(file_path)
                score_item = QTableWidgetItem(f"{score:.4f}")
                score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.results_table_widget.setItem(row, 0, path_item)
                self.results_table_widget.setItem(row, 1, score_item)
        self.find_similar_button.setEnabled(True)

    def start_clustering_and_renaming(self):
        target_dir = self.target_dir_input.text()
        if not self.orchestrator or not target_dir:
            QMessageBox.warning(self, "警告", "请先在“配置”标签页中成功配置数据库并选择目标文件夹！")
            return
        reply = QMessageBox.question(self, "确认操作", f"这将在 '{target_dir}' 目录下创建新的文件夹并复制重命名文件...\n\n您确定要继续吗？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return
        from qzen_ui.worker import Worker
        self.cluster_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        similarity_threshold = self.similarity_threshold_spinbox.value()
        self.worker = Worker(self.orchestrator.run_clustering_and_renaming, target_path=target_dir, similarity_threshold=similarity_threshold, progress_callback=self._thread_safe_progress_callback)
        self.worker.result_ready.connect(self.on_task_finished)
        self.worker.error_occurred.connect(self.on_task_error)
        self.worker.start()

    def start_filename_search(self):
        keyword = self.keyword_input.text()
        intermediate_dir = self.intermediate_dir_input.text()
        target_dir = self.target_dir_input.text()
        if not all([self.orchestrator, keyword, intermediate_dir, target_dir]):
            QMessageBox.warning(self, "警告", "请先配置数据库、选择中间/目标文件夹并输入关键词！")
            return
        from qzen_ui.worker import Worker
        self.filename_search_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.worker = Worker(self.orchestrator.run_filename_search, keyword=keyword, intermediate_path=intermediate_dir, target_path=target_dir, allowed_extensions=SUPPORTED_EXTENSIONS, progress_callback=self._thread_safe_progress_callback)
        self.worker.result_ready.connect(self.on_task_finished)
        self.worker.error_occurred.connect(self.on_task_error)
        self.worker.start()

    def start_content_search(self):
        keyword = self.keyword_input.text()
        target_dir = self.target_dir_input.text()
        if not all([self.orchestrator, keyword, target_dir]):
            QMessageBox.warning(self, "警告", "请先配置数据库、选择目标文件夹并输入关键词！")
            return
        from qzen_ui.worker import Worker
        self.content_search_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.worker = Worker(self.orchestrator.run_content_search, keyword=keyword, target_path=target_dir, progress_callback=self._thread_safe_progress_callback)
        self.worker.result_ready.connect(self.on_task_finished)
        self.worker.error_occurred.connect(self.on_task_error)
        self.worker.start()
