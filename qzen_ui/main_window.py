# -*- coding: utf-8 -*-
"""
Qzen 主窗口模块。

定义了应用程序的主界面 `MainWindow`，它是整个UI的容器和控制器。
"""

import os
import logging
from typing import Tuple, List, Callable

from PyQt6.QtWidgets import (
    QMainWindow, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QProgressBar, QListWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox, QTabWidget,
    QSpinBox, QMenu, QPlainTextEdit
)
from PyQt6.QtGui import QAction, QCloseEvent, QIcon, QGuiApplication
from PyQt6.QtCore import Qt, pyqtSignal

# 本地导入
from qzen_ui.config_dialog import ConfigDialog
from qzen_ui.worker import Worker
from qzen_data import file_handler
from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import DeduplicationResult, RenameResult, SearchResult
from qzen_utils import config_manager
from qzen_core.orchestrator import Orchestrator

SUPPORTED_EXTENSIONS = {
    '.txt', '.md', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
}

class MainWindow(QMainWindow):
    """
    应用程序主窗口类。
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

        # 初始化UI组件
        self._create_menus()
        self._create_central_widget()
        self._connect_signals()

        # 加载状态
        self._load_app_config()
        self._update_tab_states()

        self.progress_signal.connect(self.update_progress)

    def _create_menus(self):
        menu_bar = self.menuBar()
        help_menu = menu_bar.addMenu("帮助(&H)")
        self.about_action = QAction("关于 Qzen...", self)
        help_menu.addAction(self.about_action)

    def _create_central_widget(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # 创建并添加标签页
        setup_tab = self._create_setup_tab()
        processing_tab = self._create_processing_tab()
        analysis_tab = self._create_analysis_tab()
        organize_tab = self._create_organize_tab()
        keyword_search_tab = self._create_keyword_search_tab()

        self.tabs.addTab(setup_tab, "1. 配置")
        self.tabs.addTab(processing_tab, "2. 批量处理")
        self.tabs.addTab(analysis_tab, "3. 交互式分析")
        self.tabs.addTab(organize_tab, "4. 自动整理")
        self.tabs.addTab(keyword_search_tab, "5. 关键词搜索")

        # 创建底部状态栏
        status_layout = self._create_status_layout()
        main_layout.addLayout(status_layout)

    def _create_setup_tab(self) -> QWidget:
        setup_tab = QWidget()
        layout = QGridLayout(setup_tab)
        self.db_config_button = QPushButton("第一步：配置数据库")
        layout.addWidget(self.db_config_button, 0, 0, 1, 3)

        layout.addWidget(QLabel("第二步：源文件夹:"), 1, 0)
        self.source_dir_input = QLineEdit()
        self.source_dir_button = QPushButton("选择...")
        layout.addWidget(self.source_dir_input, 1, 1)
        layout.addWidget(self.source_dir_button, 1, 2)

        layout.addWidget(QLabel("第三步：中间文件夹:"), 2, 0)
        self.intermediate_dir_input = QLineEdit()
        self.intermediate_dir_button = QPushButton("选择...")
        layout.addWidget(self.intermediate_dir_input, 2, 1)
        layout.addWidget(self.intermediate_dir_button, 2, 2)

        layout.addWidget(QLabel("第四步：目标文件夹:"), 3, 0)
        self.target_dir_input = QLineEdit()
        self.target_dir_button = QPushButton("选择...")
        layout.addWidget(self.target_dir_input, 3, 1)
        layout.addWidget(self.target_dir_button, 3, 2)
        
        layout.addWidget(QLabel("--- 高级参数配置 ---"), 4, 0, 1, 3)
        max_features_label = QLabel("TF-IDF 最大特征数 (?):")
        max_features_label.setToolTip("控制用于文本分析的词汇量。\n默认值: 5000。\n处理专业领域或多种语言的文档时，可适当调高此值以提高精度，\n但这会增加内存消耗和计算时间。")
        self.max_features_spinbox = QSpinBox()
        self.max_features_spinbox.setRange(1000, 50000)
        self.max_features_spinbox.setSingleStep(1000)
        layout.addWidget(max_features_label, 5, 0)
        layout.addWidget(self.max_features_spinbox, 5, 1)

        slice_size_label = QLabel("内容切片大小 (KB) (?):")
        slice_size_label.setToolTip("为计算文档相似度而提取的文档首尾部分的大小。\n默认值: 1 KB。\n增加此值可以更准确地代表长文档的核心内容，但同样会增加内存和计算开销。")
        self.slice_size_spinbox = QSpinBox()
        self.slice_size_spinbox.setRange(1, 10)
        layout.addWidget(slice_size_label, 6, 0)
        layout.addWidget(self.slice_size_spinbox, 6, 1)

        stopwords_label = QLabel("自定义停用词 (?):")
        stopwords_label.setToolTip("在此输入您希望在所有文本分析中忽略的词语（如公司名、产品名），每行一个。")
        self.custom_stopwords_input = QPlainTextEdit()
        layout.addWidget(stopwords_label, 7, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.custom_stopwords_input, 7, 1, 1, 2)

        self.edit_stopwords_button = QPushButton("编辑")
        self.save_stopwords_button = QPushButton("保存并应用")

        stopwords_button_layout = QHBoxLayout()
        stopwords_button_layout.addStretch()
        stopwords_button_layout.addWidget(self.edit_stopwords_button)
        stopwords_button_layout.addWidget(self.save_stopwords_button)

        layout.addLayout(stopwords_button_layout, 8, 1, 1, 2)
        
        # 设置自定义停用词区域的初始状态
        self.custom_stopwords_input.setReadOnly(True)
        self.save_stopwords_button.hide()

        layout.setRowStretch(9, 1)
        return setup_tab

    def _create_processing_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.deduplicate_button = QPushButton("执行去重与预处理")
        self.vectorize_button = QPushButton("执行向量化")
        layout.addWidget(self.deduplicate_button)
        layout.addWidget(self.vectorize_button)
        
        self.deduplication_results_widget = QListWidget()
        self.deduplication_results_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(QLabel("去重结果 (重复文件列表):"))
        layout.addWidget(self.deduplication_results_widget)
        return tab

    def _create_analysis_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        file_list_layout = QVBoxLayout()
        self.load_files_button = QPushButton("加载文件列表并预热引擎")
        self.file_list_widget = QListWidget()
        self.find_similar_button = QPushButton("查找相似文件")
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
        self.results_table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        results_layout.addWidget(self.results_table_widget)
        
        layout.addLayout(file_list_layout, 1)
        layout.addLayout(results_layout, 2)
        return tab

    def _create_organize_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("相似度阈值:"))
        self.similarity_threshold_spinbox = QDoubleSpinBox()
        self.similarity_threshold_spinbox.setRange(0.0, 1.0)
        self.similarity_threshold_spinbox.setSingleStep(0.05)
        self.similarity_threshold_spinbox.setValue(0.85)
        self.cluster_button = QPushButton("相似文件按主题自动分组")
        controls_layout.addWidget(self.similarity_threshold_spinbox)
        controls_layout.addWidget(self.cluster_button)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        self.rename_results_table_widget = QTableWidget()
        self.rename_results_table_widget.setColumnCount(2)
        self.rename_results_table_widget.setHorizontalHeaderLabels(["原文件路径", "归组后文件夹"])
        self.rename_results_table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.rename_results_table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(QLabel("自动分组结果:"))
        layout.addWidget(self.rename_results_table_widget)
        return tab

    def _create_keyword_search_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        input_layout = QHBoxLayout()
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("在此输入关键词...")
        input_layout.addWidget(QLabel("关键词:"))
        input_layout.addWidget(self.keyword_input)
        
        self.filename_search_button = QPushButton("按文件名搜索")
        self.content_search_button = QPushButton("按文件内容搜索")
        layout.addLayout(input_layout)
        layout.addWidget(self.filename_search_button)
        layout.addWidget(self.content_search_button)
        
        self.keyword_search_results_widget = QListWidget()
        self.keyword_search_results_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(QLabel("搜索结果:"))
        layout.addWidget(self.keyword_search_results_widget)
        return tab

    def _create_status_layout(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.cancel_button = QPushButton("取消任务")
        self.cancel_button.setVisible(False)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.cancel_button)
        return layout

    def _connect_signals(self):
        # 菜单
        self.about_action.triggered.connect(self.show_about_dialog)

        self.save_stopwords_button.clicked.connect(self._apply_and_save_stopwords)
        self.edit_stopwords_button.clicked.connect(self._enter_stopwords_edit_mode)

        # 1. 配置
        self.db_config_button.clicked.connect(self.show_db_config_dialog)
        self.source_dir_button.clicked.connect(lambda: self._select_directory(self.source_dir_input, "选择源文件夹"))
        self.intermediate_dir_button.clicked.connect(lambda: self._select_directory(self.intermediate_dir_input, "选择中间文件夹"))
        self.target_dir_button.clicked.connect(lambda: self._select_directory(self.target_dir_input, "选择目标文件夹"))

        # 2. 批量处理
        self.deduplicate_button.clicked.connect(self.start_deduplication)
        self.vectorize_button.clicked.connect(self.start_vectorization)
        self.deduplication_results_widget.customContextMenuRequested.connect(self._show_context_menu)

        # 3. 交互式分析
        self.load_files_button.clicked.connect(self.load_intermediate_files)
        self.file_list_widget.itemSelectionChanged.connect(self.update_button_states)
        self.find_similar_button.clicked.connect(self.on_find_similar_clicked)
        self.results_table_widget.customContextMenuRequested.connect(self._show_context_menu)

        # 4. 自动整理
        self.cluster_button.clicked.connect(self.start_topic_clustering)
        self.rename_results_table_widget.customContextMenuRequested.connect(self._show_context_menu)

        # 5. 关键词搜索
        self.filename_search_button.clicked.connect(self.start_filename_search)
        self.content_search_button.clicked.connect(self.start_content_search)
        self.keyword_search_results_widget.customContextMenuRequested.connect(self._show_context_menu)

    def _enter_stopwords_edit_mode(self):
        """切换到自定义停用词的编辑模式。"""
        self.custom_stopwords_input.setReadOnly(False)
        self.custom_stopwords_input.setStyleSheet("")  # 恢复默认外观
        self.edit_stopwords_button.hide()
        self.save_stopwords_button.show()

    def _leave_stopwords_edit_mode(self):
        """退出自定义停用词的编辑模式，恢复到只读状态。"""
        self.custom_stopwords_input.setReadOnly(True)
        self.save_stopwords_button.hide()
        self.edit_stopwords_button.show()

    def _apply_and_save_stopwords(self):
        """保存并应用新的自定义停用词列表。"""
        # 1. 保存配置
        self._save_app_config()

        # 2. 热更新业务逻辑核心
        if self.orchestrator:
            custom_stopwords_text = self.custom_stopwords_input.toPlainText()
            custom_stopwords = [word.strip() for word in custom_stopwords_text.splitlines() if word.strip()]
            self.orchestrator.update_stopwords(custom_stopwords)
            QMessageBox.information(self, "成功", "自定义停用词已更新并对后续任务生效！")
        else:
            QMessageBox.warning(self, "提示", "自定义停用词已保存，将在您配置数据库后生效。")

        # 3. 切换回只读模式
        self._leave_stopwords_edit_mode()

    def show_about_dialog(self):
        QMessageBox.about(self, "关于 Qzen (千针)", "<p><b>Qzen (千针) v1.0</b></p><p>本地文档智能整理客户端。</p>")

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
        self.max_features_spinbox.setValue(config.get("max_features", 5000))
        self.slice_size_spinbox.setValue(config.get("slice_size_kb", 1))
        self.custom_stopwords_input.setPlainText(config.get("custom_stopwords", ""))

    def _save_app_config(self):
        config = {
            "source_dir": self.source_dir_input.text(),
            "intermediate_dir": self.intermediate_dir_input.text(),
            "target_dir": self.target_dir_input.text(),
            "similarity_threshold": self.similarity_threshold_spinbox.value(),
            "last_keyword": self.keyword_input.text(),
            "max_features": self.max_features_spinbox.value(),
            "slice_size_kb": self.slice_size_spinbox.value(),
            "custom_stopwords": self.custom_stopwords_input.toPlainText()
        }
        config_manager.save_config(config)

    def closeEvent(self, event: QCloseEvent):
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

    def _reset_task_ui_state(self):
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.cancel_button.setText("取消任务")
        self.deduplicate_button.setEnabled(True)
        self.vectorize_button.setEnabled(True)
        self.cluster_button.setEnabled(True)
        self.filename_search_button.setEnabled(True)
        self.content_search_button.setEnabled(True)
        self.update_button_states()
        try:
            self.cancel_button.clicked.disconnect(self.cancel_current_task)
        except TypeError:
            pass

    def on_task_finished(self, message: str):
        self._reset_task_ui_state()
        self.setWindowTitle("Qzen (千针) - 本地文档智能整理")
        QMessageBox.information(self, "完成", message)

    def on_vectorization_finished(self, message: str):
        self.on_task_finished(message)
        self._is_vectorized = True
        self._update_tab_states()

    def on_task_error(self, error: Exception):
        logging.error(f"后台任务线程发生异常: {error}", exc_info=True)
        self._reset_task_ui_state()
        self.setWindowTitle("Qzen (千针) - 本地文档智能整理")
        QMessageBox.critical(self, "错误", f"任务执行失败！\n错误信息: {error}")

    def on_task_cancelled(self):
        logging.info("UI层确认任务已取消。")
        self._reset_task_ui_state()
        self.setWindowTitle("Qzen (千针) - 任务已取消")
        QMessageBox.warning(self, "任务已取消", "操作已由用户中止。")

    def cancel_current_task(self):
        logging.info("UI层发出取消任务请求。")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("正在取消...")
        if self.worker:
            self.worker.cancel()

    def _start_task(self, target_function: Callable, on_result_slot: Callable, *args, **kwargs):
        self.deduplicate_button.setEnabled(False)
        self.vectorize_button.setEnabled(False)
        self.cluster_button.setEnabled(False)
        self.filename_search_button.setEnabled(False)
        self.content_search_button.setEnabled(False)
        self.find_similar_button.setEnabled(False)

        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.cancel_button.setVisible(True)
        self.cancel_button.setEnabled(True)

        self.worker = Worker(target_function, *args, **kwargs)
        self.worker.result_ready.connect(on_result_slot)
        self.worker.error_occurred.connect(self.on_task_error)
        self.worker.cancelled.connect(self.on_task_cancelled)
        self.cancel_button.clicked.connect(self.cancel_current_task)
        
        self.worker.start()

    def show_db_config_dialog(self):
        dialog = ConfigDialog(self)
        if not dialog.exec():
            return

        db_url = dialog.get_db_url()
        self.db_handler = DatabaseHandler(db_url)

        # 从UI读取自定义停用词
        custom_stopwords_text = self.custom_stopwords_input.toPlainText()
        custom_stopwords = [word.strip() for word in custom_stopwords_text.splitlines() if word.strip()]

        self.orchestrator = Orchestrator(
            db_handler=self.db_handler,
            max_features=self.max_features_spinbox.value(),
            slice_size_kb=self.slice_size_spinbox.value(),
            custom_stopwords=custom_stopwords
        )

        try:
            if not self.db_handler.test_connection():
                raise ConnectionError("无法连接到数据库，请检查配置信息。")
            QMessageBox.information(self, "成功", "数据库连接成功！")
            self._update_tab_states()
        except Exception as e:
            QMessageBox.critical(self, "数据库初始化失败", f"无法完成数据库的设置。\n错误: {e}")
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
            self.orchestrator.prepare_deduplication_workspace(intermediate_dir)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"准备工作空间失败！\n错误: {e}")
            return

        self.deduplication_results_widget.clear()
        self._start_task(
            self.orchestrator.run_deduplication_core,
            self.on_deduplication_finished,
            source_path=source_dir, 
            intermediate_path=intermediate_dir, 
            allowed_extensions=SUPPORTED_EXTENSIONS, 
            progress_callback=self._thread_safe_progress_callback
        )
    
    def on_deduplication_finished(self, result: Tuple[str, List[DeduplicationResult]]):
        summary, results = result
        self.deduplication_results_widget.clear()
        if not results:
            self.deduplication_results_widget.addItem("没有发现重复文件。")
        else:
            for item in results:
                self.deduplication_results_widget.addItem(item.duplicate_file_path)
        self.on_task_finished(summary)

    def start_vectorization(self):
        if not self.orchestrator:
            QMessageBox.warning(self, "警告", "请先在“配置”标签页中成功配置数据库！")
            return
        self._start_task(
            self.orchestrator.run_vectorization,
            self.on_vectorization_finished,
            progress_callback=self._thread_safe_progress_callback
        )

    def load_intermediate_files(self):
        intermediate_dir = self.intermediate_dir_input.text()
        if not intermediate_dir or not self.orchestrator:
            QMessageBox.warning(self, "警告", "请先配置数据库并选择中间文件夹！")
            return
        self.file_list_widget.clear()
        for file_path in file_handler.scan_files(intermediate_dir, SUPPORTED_EXTENSIONS):
            self.file_list_widget.addItem(file_path)
        self._start_task(self.orchestrator.prime_similarity_engine, lambda: self.on_task_finished("相似度引擎已预热完成！"))

    def on_find_similar_clicked(self):
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items:
            return
        self._start_task(
            self.orchestrator.find_top_n_similar_for_file,
            self.on_search_complete,
            target_file_path=selected_items[0].text(),
            n=10
        )

    def on_search_complete(self, results: list):
        self.results_table_widget.setRowCount(0)
        if not results:
            QMessageBox.information(self, "提示", "没有找到相似的文件。")
        else:
            self.results_table_widget.setRowCount(len(results))
            for row, (file_path, score) in enumerate(results):
                self.results_table_widget.setItem(row, 0, QTableWidgetItem(file_path))
                self.results_table_widget.setItem(row, 1, QTableWidgetItem(f"{score:.4f}"))
        self.on_task_finished("查找相似文件完成。")

    def start_topic_clustering(self):
        target_dir = self.target_dir_input.text()
        if not self.orchestrator or not target_dir:
            QMessageBox.warning(self, "警告", "请先配置数据库并选择目标文件夹！")
            return
        reply = QMessageBox.question(self, "确认操作", f"这将在 '{target_dir}' 目录下创建以主题命名的文件夹，并复制相关文件（原始文件名不变）。\n\n您确定要继续吗？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return
        self.rename_results_table_widget.setRowCount(0)
        self._start_task(
            self.orchestrator.run_topic_clustering,
            self.on_clustering_finished,
            target_path=target_dir,
            similarity_threshold=self.similarity_threshold_spinbox.value(),
            progress_callback=self._thread_safe_progress_callback
        )

    def on_clustering_finished(self, result: Tuple[str, List[RenameResult]]):
        summary, results = result
        self.rename_results_table_widget.setRowCount(0)
        if results:
            self.rename_results_table_widget.setRowCount(len(results))
            for row, item in enumerate(results):
                self.rename_results_table_widget.setItem(row, 0, QTableWidgetItem(item.original_file_path))
                new_folder_path = os.path.dirname(item.new_file_path)
                self.rename_results_table_widget.setItem(row, 1, QTableWidgetItem(new_folder_path))
        self.on_task_finished(summary)

    def start_filename_search(self):
        keyword = self.keyword_input.text()
        intermediate_dir = self.intermediate_dir_input.text()
        target_dir = self.target_dir_input.text()
        if not all([self.orchestrator, keyword, intermediate_dir, target_dir]):
            QMessageBox.warning(self, "警告", "请先配置数据库、选择中间/目标文件夹并输入关键词！")
            return
        self.keyword_search_results_widget.clear()
        self._start_task(
            self.orchestrator.run_filename_search,
            self.on_keyword_search_finished,
            keyword=keyword,
            intermediate_path=intermediate_dir,
            target_path=target_dir,
            allowed_extensions=SUPPORTED_EXTENSIONS,
            progress_callback=self._thread_safe_progress_callback
        )

    def start_content_search(self):
        keyword = self.keyword_input.text()
        target_dir = self.target_dir_input.text()
        if not all([self.orchestrator, keyword, target_dir]):
            QMessageBox.warning(self, "警告", "请先配置数据库、选择目标文件夹并输入关键词！")
            return
        self.keyword_search_results_widget.clear()
        self._start_task(
            self.orchestrator.run_content_search,
            self.on_keyword_search_finished,
            keyword=keyword,
            target_path=target_dir,
            progress_callback=self._thread_safe_progress_callback
        )

    def on_keyword_search_finished(self, result: Tuple[str, List[SearchResult]]):
        summary, results = result
        self.keyword_search_results_widget.clear()
        if not results:
            self.keyword_search_results_widget.addItem("没有找到匹配的文件。")
        else:
            for item in results:
                self.keyword_search_results_widget.addItem(item.matched_file_path)
        self.on_task_finished(summary)

    def _show_context_menu(self, point):
        sender_widget = self.sender()
        if sender_widget is None:
            return

        file_path = self._get_filepath_from_widget(sender_widget, point)
        if not file_path or not os.path.exists(os.path.dirname(file_path)):
            return

        menu = QMenu()
        open_folder_action = QAction("打开文件所在目录", self)
        copy_path_action = QAction("复制文件路径", self)
        
        open_folder_action.triggered.connect(lambda: self._open_folder_for_item(file_path))
        copy_path_action.triggered.connect(lambda: self._copy_path_for_item(file_path))

        menu.addAction(open_folder_action)
        menu.addAction(copy_path_action)
        menu.exec(sender_widget.mapToGlobal(point))

    def _get_filepath_from_widget(self, widget: QWidget, point) -> str | None:
        file_path = None
        if isinstance(widget, QListWidget):
            item = widget.itemAt(point)
            if item:
                file_path = item.text()
        elif isinstance(widget, QTableWidget):
            item = widget.itemAt(point)
            if item:
                # 对于重命名结果表格，新文件路径在第1列
                col = 1 if widget is self.rename_results_table_widget else 0
                path_item = widget.item(item.row(), col)
                if path_item:
                    file_path = path_item.text()
        return file_path

    def _open_folder_for_item(self, file_path: str):
        try:
            # 使用 os.path.normpath 确保路径格式正确
            os.startfile(os.path.dirname(os.path.normpath(file_path)))
        except Exception as e:
            logging.error(f"无法打开文件夹: {e}")
            QMessageBox.warning(self, "错误", f"无法打开文件夹：\n{os.path.dirname(file_path)}")

    def _copy_path_for_item(self, file_path: str):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(file_path)
        logging.info(f"路径已复制到剪贴板: {file_path}")
