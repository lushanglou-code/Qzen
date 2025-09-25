# -*- coding: utf-8 -*-
"""
Qzen 主窗口模块 (v5.1.3 - 强制重编译)。

此版本通过添加一个虚拟方法来强制 Python 解释器重新编译文件，
以解决因缓存 (.pyc) 问题而导致的、已修复的导入错误反复出现的问题。
"""

from __future__ import annotations # PEP 563: Solves circular import issues with type hints.

import logging
import os
from typing import Dict, Any, List, Callable, Tuple

from PyQt6.QtWidgets import (
    QMainWindow, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, 
    QFileDialog, QProgressBar, QTabWidget, QPushButton
)
from PyQt6.QtGui import QAction, QCloseEvent
from PyQt6.QtCore import pyqtSignal

# --- v4.0.0 架构引入 ---
from qzen_core.orchestrator import Orchestrator
from qzen_core.analysis_service import AnalysisService

# --- v4.0.0 UI模块导入 ---
from qzen_ui.tabs.setup_tab import SetupTab
from qzen_ui.tabs.processing_tab import ProcessingTab
from qzen_ui.tabs.analysis_cluster_tab import AnalysisClusterTab
from qzen_ui.tabs.keyword_search_tab import KeywordSearchTab

# --- 其他辅助模块导入 ---
from qzen_ui.config_dialog import ConfigDialog
from qzen_ui.worker import Worker
from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Document, DeduplicationResult
from qzen_utils import config_manager


class MainWindow(QMainWindow):
    """
    应用程序主窗口类。
    """
    progress_signal = pyqtSignal(int, int, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.db_handler: DatabaseHandler | None = None
        self.orchestrator: Orchestrator | None = None
        self.analysis_service: AnalysisService | None = None
        self.worker: Worker | None = None

        self.setWindowTitle("Qzen (千针) v5.1 - 智能文档组织引擎 (MySQL/PyMySQL 版)")
        self.setGeometry(100, 100, 1200, 800)

        self._create_menus()
        self._create_central_widget()
        self._connect_signals()

        self._load_app_config()
        self._update_tab_states()

        self.progress_signal.connect(self.update_progress)
        self._force_recompile_workaround() # v5.1.3: Call dummy method

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

        self.setup_tab = SetupTab()
        self.processing_tab = ProcessingTab()
        self.analysis_cluster_tab = AnalysisClusterTab()
        self.keyword_search_tab = KeywordSearchTab()

        self.tabs.addTab(self.setup_tab, "1. 配置")
        self.tabs.addTab(self.processing_tab, "2. 数据摄取")
        self.tabs.addTab(self.analysis_cluster_tab, "3. 分析与聚类")
        self.tabs.addTab(self.keyword_search_tab, "4. 关键词搜索")

        status_layout = self._create_status_layout()
        main_layout.addLayout(status_layout)

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
        self.about_action.triggered.connect(self.show_about_dialog)
        self.setup_tab.db_config_clicked.connect(self.show_db_config_dialog)
        self.setup_tab.select_source_dir_clicked.connect(lambda: self._select_directory(self.setup_tab, "source_dir_input", "选择源文件夹"))
        self.setup_tab.select_intermediate_dir_clicked.connect(lambda: self._select_directory(self.setup_tab, "intermediate_dir_input", "选择中间文件夹"))
        self.setup_tab.select_target_dir_clicked.connect(lambda: self._select_directory(self.setup_tab, "target_dir_input", "选择目标文件夹"))
        self.setup_tab.save_stopwords_clicked.connect(self._save_app_config)
        self.processing_tab.start_ingestion_clicked.connect(self.start_ingestion)
        
        self.analysis_cluster_tab.run_kmeans_clicked.connect(self.start_kmeans_clustering)
        self.analysis_cluster_tab.run_similarity_clicked.connect(self.start_similarity_clustering)
        self.analysis_cluster_tab.select_source_file_clicked.connect(self._select_source_file)
        self.analysis_cluster_tab.find_similar_clicked.connect(self.find_similar_files)
        self.analysis_cluster_tab.export_similar_clicked.connect(self.export_similar_files)
        
        self.keyword_search_tab.search_by_filename_clicked.connect(self.start_filename_search)
        self.keyword_search_tab.search_by_content_clicked.connect(self.start_content_search)
        self.keyword_search_tab.export_results_clicked.connect(self.export_search_results)

    def _load_app_config(self):
        config = config_manager.load_config()
        self.setup_tab.set_all_configs(config)
        self.keyword_search_tab.set_config(config)
        self.analysis_cluster_tab.similarity_threshold_spinbox.setValue(config.get("similarity_threshold", 0.85))
        intermediate_dir = config.get("intermediate_dir", "")
        self.analysis_cluster_tab.set_cluster_target_dir(intermediate_dir)

    def _save_app_config(self):
        config = self.setup_tab.get_all_configs()
        config["last_keyword"] = self.keyword_search_tab.get_keyword()
        config["similarity_threshold"] = self.analysis_cluster_tab.similarity_threshold_spinbox.value()
        config_manager.save_config(config)

    def closeEvent(self, event: QCloseEvent):
        self._save_app_config()
        super().closeEvent(event)

    def show_about_dialog(self):
        QMessageBox.about(self, "关于 Qzen (千针)", "<p><b>Qzen (千针) v5.1 (MySQL/PyMySQL 版)</b></p><p>智能文档组织引擎。</p>")

    def _update_tab_states(self):
        is_db_configured = self.orchestrator is not None
        self.tabs.setTabEnabled(1, is_db_configured)
        self.tabs.setTabEnabled(2, is_db_configured)
        self.tabs.setTabEnabled(3, is_db_configured)

    def _select_directory(self, tab: QWidget, line_edit_name: str, caption: str):
        directory = QFileDialog.getExistingDirectory(self, caption)
        if directory:
            if hasattr(tab, 'set_path_text'):
                tab.set_path_text(line_edit_name, directory)
            if line_edit_name == "intermediate_dir_input":
                self.analysis_cluster_tab.set_cluster_target_dir(directory)

    def show_db_config_dialog(self):
        """
        v5.1 迁移: 使用 PyMySQL 驱动以解决二进制冲突。
        """
        # 假定数据库名为 'qzen_db'，请确保它已在 MySQL 中创建。
        db_url = "mysql+pymysql://root:12345678@127.0.0.1:3306/qzen_db"
        logging.info(f"正在使用硬编码的 MySQL 数据库连接 (通过 PyMySQL): {db_url}")

        config = self.setup_tab.get_all_configs()
        try:
            self.db_handler = DatabaseHandler(db_url)
            if not self.db_handler.test_connection():
                QMessageBox.critical(self, "连接失败", "无法连接到 MySQL 数据库。\n请确保：\n1. MySQL 服务正在运行。\n2. 用户名、密码、IP和端口正确。\n3. 数据库 'qzen_db' 已被创建。")
                return

            self.orchestrator = Orchestrator(
                db_handler=self.db_handler,
                max_features=config.get("max_features", 5000),
                slice_size_kb=config.get("slice_size_kb", 1024),
                custom_stopwords=config.get('custom_stopwords', '').splitlines()
            )
            self.analysis_service = AnalysisService(self.db_handler, self.orchestrator)

            QMessageBox.information(self, "成功", "MySQL 数据库连接成功，所有服务已准备就绪！")
        except Exception as e:
            QMessageBox.critical(self, "初始化失败", f"无法完成数据库或服务的设置。\n错误: {e}")
            self.db_handler = None
            self.orchestrator = None
            self.analysis_service = None
        finally:
            self._update_tab_states()

    # --- 阶段二：数据摄取 ---
    def start_ingestion(self):
        if not self.orchestrator: return
        configs = self.setup_tab.get_all_configs()
        source_dir, intermediate_dir = configs["source_dir"], configs["intermediate_dir"]
        if not all([source_dir, intermediate_dir]):
            QMessageBox.warning(self, "警告", "请选择源文件夹和中间文件夹！")
            return

        reply = QMessageBox.question(self, "确认操作", f"此操作将清空数据库和中间文件夹 '{intermediate_dir}'。\n确定要开始吗？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return

        self.processing_tab.clear_results()
        try:
            self.orchestrator.prepare_deduplication_workspace(intermediate_dir)
            self.processing_tab.append_result("工作空间已准备就绪。")
            self._start_task(self.orchestrator.run_deduplication_core, self.on_deduplication_finished, source_path=source_dir, intermediate_path=intermediate_dir, allowed_extensions={ext.strip() for ext in configs.get("allowed_extensions", ".pdf,.docx,.txt").split(',') if ext.strip()})
        except Exception as e:
            self.on_task_error(e)

    def on_deduplication_finished(self, result: Tuple[str, List[DeduplicationResult]]):
        summary, _ = result
        self.processing_tab.append_result(summary)
        self.processing_tab.append_result("去重完成，现在开始向量化...")
        self._start_task(self.orchestrator.run_vectorization, self.on_vectorization_finished)

    def on_vectorization_finished(self, summary: str):
        self.processing_tab.append_result(summary)
        self.on_task_finished("数据摄取流程成功完成！")

    # --- 阶段三：聚类 (v4.0.0 架构重构) ---
    def start_kmeans_clustering(self, target_dir: str, k: int):
        if not self.orchestrator: return
        reply = QMessageBox.question(self, "确认 K-Means 聚类", f"确定要对文件夹 '{os.path.basename(target_dir)}' 及其所有子文件夹执行 K-Means 聚类 (K={k}) 吗？\n此操作将重塑该文件夹的内部结构。", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        self._start_task(self.orchestrator.run_kmeans_clustering, self.on_clustering_finished, target_dir=target_dir, k=k)

    def start_similarity_clustering(self, target_dir: str, threshold: float):
        if not self.orchestrator: return
        reply = QMessageBox.question(self, "确认相似度分组", f"确定要对文件夹 '{os.path.basename(target_dir)}' 及其所有子文件夹执行相似度分组 (阈值={threshold}) 吗？\n此操作将重塑该文件夹的内部结构。", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        self._start_task(self.orchestrator.run_similarity_clustering, self.on_clustering_finished, target_dir=target_dir, threshold=threshold)

    def on_clustering_finished(self, summary: str):
        final_message = f"本轮聚类操作已成功完成！\n{summary}\n\n您现在可以打开文件浏览器查看整理好的文件夹。"
        self.on_task_finished(final_message)

    # --- 阶段四：关键词搜索 ---
    def start_filename_search(self, keyword: str):
        if not self.analysis_service: return
        self._start_task(self.analysis_service.search_by_filename, self.on_search_finished, keyword=keyword)

    def start_content_search(self, keyword: str):
        if not self.analysis_service: return
        self._start_task(self.analysis_service.search_by_content, self.on_search_finished, keyword=keyword)

    def on_search_finished(self, results: List[Document]):
        self.keyword_search_tab.display_results(results)
        self.on_task_finished(f"关键词搜索完成，共找到 {len(results)} 个结果。")

    def export_search_results(self, doc_ids: List[int], keyword: str):
        if not self.analysis_service: return
        target_dir = self.setup_tab.get_all_configs()["target_dir"]
        if not target_dir:
            QMessageBox.warning(self, "警告", "请先在“配置”中指定目标文件夹！")
            return
        self._start_task(self.analysis_service.export_search_results, self.on_export_finished, doc_ids=doc_ids, keyword=keyword, export_base_dir=target_dir)

    # --- 阶段五：相似文件分析 ---
    def _select_source_file(self):
        if not self.db_handler: return
        intermediate_dir = self.setup_tab.get_all_configs().get("intermediate_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(self, "选择源文件", intermediate_dir, "All Files (*)")
        if not file_path: return

        doc = self.db_handler.get_document_by_path(file_path)
        if doc:
            self.analysis_cluster_tab.set_source_file(doc.file_path, doc.id)
        else:
            QMessageBox.warning(self, "错误", "无法在数据库中找到该文件的记录。\n请确保该文件位于中间文件夹内，且数据摄取已完成。")

    def find_similar_files(self, source_file_id: int, top_n: int):
        if not self.analysis_service: return
        self._start_task(self.analysis_service.find_similar_to_file, self.on_find_similar_finished, file_id=source_file_id, top_n=top_n)

    def on_find_similar_finished(self, results: List[Dict[str, Any]]):
        self.analysis_cluster_tab.display_similar_results(results)
        self.on_task_finished(f"为选中文件找到了 {len(results)} 个相似项。")

    def export_similar_files(self, doc_ids: List[int], source_file_path: str):
        if not self.analysis_service: return
        target_dir = self.setup_tab.get_all_configs()["target_dir"]
        if not target_dir:
            QMessageBox.warning(self, "警告", "请先在“配置”中指定目标文件夹！")
            return
        
        source_filename = os.path.splitext(os.path.basename(source_file_path))[0]
        destination_dir = os.path.join(target_dir, f"{source_filename}_相似文件")
        
        self._start_task(self.analysis_service.export_files_by_ids, self.on_export_finished, doc_ids=doc_ids, destination_dir=destination_dir)

    def on_export_finished(self, export_path: str):
        if not export_path: return
        self.on_task_finished(f"结果已成功导出到: {export_path}")
        try:
            os.startfile(export_path)
        except Exception as e:
            logging.error(f"无法自动打开导出文件夹: {e}")

    # --- 后台任务管理框架 ---
    def _start_task(self, target_function: Callable, on_result_slot: Callable, *args, **kwargs):
        self.tabs.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.cancel_button.setVisible(True)
        self.cancel_button.setEnabled(True)

        if "progress_callback" in target_function.__code__.co_varnames:
            kwargs["progress_callback"] = self.progress_signal.emit

        self.worker = Worker(target_function, *args, **kwargs)
        
        if on_result_slot.__code__.co_argcount > 1:
             self.worker.result_ready.connect(on_result_slot)
        else:
             self.worker.finished.connect(on_result_slot)

        self.worker.error_occurred.connect(self.on_task_error)
        self.worker.cancelled.connect(self.on_task_cancelled)
        self.cancel_button.clicked.connect(self.cancel_current_task)
        self.worker.start()

    def _reset_task_ui_state(self):
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.cancel_button.setText("取消任务")
        self.tabs.setEnabled(True)
        try:
            self.cancel_button.clicked.disconnect(self.cancel_current_task)
        except TypeError:
            pass

    def on_task_finished(self, message: str):
        self._reset_task_ui_state()
        QMessageBox.information(self, "完成", message)

    def on_task_error(self, error: Exception):
        logging.error(f"后台任务线程发生异常: {error}", exc_info=True)
        self._reset_task_ui_state()
        QMessageBox.critical(self, "错误", f"任务执行失败！\n错误信息: {error}")

    def on_task_cancelled(self):
        logging.info("UI层确认任务已取消。")
        self._reset_task_ui_state()
        QMessageBox.warning(self, "任务已取消", "操作已由用户中止。")

    def cancel_current_task(self):
        logging.info("UI层发出取消任务请求。")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("正在取消...")
        if self.worker:
            self.worker.cancel()

    def update_progress(self, current_value: int, max_value: int, status_text: str):
        self.progress_bar.setMaximum(max_value)
        self.progress_bar.setValue(current_value)
        self.setWindowTitle(f"Qzen (千针) v5.1 - {status_text}")

    def _force_recompile_workaround(self):
        """ v5.1.3: This dummy method forces a recompile to avoid .pyc cache issues. """
        pass
