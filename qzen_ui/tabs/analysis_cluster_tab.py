# -*- coding: utf-8 -*-
"""
UI 模块：分析与聚类标签页 (v4.0.1 - 路径规范化修复)。

此版本修复了 UI 层路径显示和处理不一致的问题。
之前，从 QFileDialog 获取的路径（在 Windows 上可能使用'/'）被直接使用，
导致向后端传递了非原生的路径格式。

本次修复通过在接收路径的函数（`_on_select_cluster_target_dir` 和 `set_source_file`）
中立即使用 `os.path.normpath()`，确保了 UI 显示和传递给后端的路径始终是
当前操作系统的原生格式 (e.g., 'E:\\folder')，从根源上保证了路径的一致性。
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSpinBox, 
    QDoubleSpinBox, QLineEdit, QFileDialog, QGroupBox, QTableWidget, 
    QTableWidgetItem, QHeaderView, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from typing import List, Dict, Any

class AnalysisClusterTab(QWidget):
    """
    封装了“分析与聚类”标签页的所有 UI 控件和布局。
    """
    run_kmeans_clicked = pyqtSignal(str, int)
    run_similarity_clicked = pyqtSignal(str, float)
    
    select_source_file_clicked = pyqtSignal()
    find_similar_clicked = pyqtSignal(int, int)
    export_similar_clicked = pyqtSignal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cluster_target_dir = ""
        self.source_file_path = ""
        self.source_file_id = -1
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """创建并布局所有 UI 控件。"""
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._create_atomic_clustering_group())
        main_layout.addWidget(self._create_similarity_analysis_group())
        main_layout.addStretch()

    def _create_atomic_clustering_group(self) -> QGroupBox:
        """创建原子化聚类功能区。"""
        group_box = QGroupBox("原子化聚类操作")
        layout = QVBoxLayout()

        target_dir_layout = QHBoxLayout()
        target_dir_layout.addWidget(QLabel("聚类目标文件夹:"))
        self.cluster_target_dir_line_edit = QLineEdit()
        self.cluster_target_dir_line_edit.setPlaceholderText("请点击右侧按钮选择一个文件夹作为聚类目标...")
        self.cluster_target_dir_line_edit.setReadOnly(True)
        self.select_cluster_target_dir_button = QPushButton("选择文件夹...")
        target_dir_layout.addWidget(self.cluster_target_dir_line_edit)
        target_dir_layout.addWidget(self.select_cluster_target_dir_button)

        kmeans_layout = QHBoxLayout()
        kmeans_layout.addWidget(QLabel("K-Means K值:"))
        self.k_spinbox = QSpinBox()
        self.k_spinbox.setRange(2, 100)
        self.k_spinbox.setValue(3)
        kmeans_layout.addWidget(self.k_spinbox)
        self.run_kmeans_button = QPushButton("执行 K-Means 聚类")
        kmeans_layout.addWidget(self.run_kmeans_button)
        kmeans_layout.addStretch()

        similarity_layout = QHBoxLayout()
        similarity_layout.addWidget(QLabel("相似度阈值:"))
        self.similarity_threshold_spinbox = QDoubleSpinBox()
        self.similarity_threshold_spinbox.setRange(0.1, 1.0)
        self.similarity_threshold_spinbox.setSingleStep(0.05)
        self.similarity_threshold_spinbox.setValue(0.85)
        similarity_layout.addWidget(self.similarity_threshold_spinbox)
        self.run_similarity_button = QPushButton("执行相似度分组")
        similarity_layout.addWidget(self.run_similarity_button)
        similarity_layout.addStretch()

        layout.addLayout(target_dir_layout)
        layout.addLayout(kmeans_layout)
        layout.addLayout(similarity_layout)
        group_box.setLayout(layout)
        return group_box

    def _create_similarity_analysis_group(self) -> QGroupBox:
        """创建相似文件分析功能区。"""
        group_box = QGroupBox("相似文件分析")
        layout = QVBoxLayout()

        source_file_layout = QHBoxLayout()
        source_file_layout.addWidget(QLabel("源文件:"))
        self.source_file_line_edit = QLineEdit()
        self.source_file_line_edit.setPlaceholderText("请点击右侧按钮选择一个文件作为分析的基准...")
        self.source_file_line_edit.setReadOnly(True)
        self.select_source_file_button = QPushButton("选择文件...")
        source_file_layout.addWidget(self.source_file_line_edit)
        source_file_layout.addWidget(self.select_source_file_button)

        analysis_controls_layout = QHBoxLayout()
        analysis_controls_layout.addWidget(QLabel("查找 Top N:"))
        self.top_n_spinbox = QSpinBox()
        self.top_n_spinbox.setRange(1, 100)
        self.top_n_spinbox.setValue(10)
        analysis_controls_layout.addWidget(self.top_n_spinbox)
        self.find_similar_button = QPushButton("查找相似文件")
        analysis_controls_layout.addWidget(self.find_similar_button)
        analysis_controls_layout.addStretch()

        results_controls_layout = QHBoxLayout()
        self.select_all_similar_checkbox = QCheckBox("全选/全不选")
        results_controls_layout.addWidget(self.select_all_similar_checkbox)
        results_controls_layout.addStretch()

        self.similar_results_table = QTableWidget()
        self.similar_results_table.setColumnCount(3)
        self.similar_results_table.setHorizontalHeaderLabels(["选择", "文件路径", "相似度"])
        self.similar_results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.similar_results_table.setColumnWidth(0, 50)
        self.similar_results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.export_similar_button = QPushButton("导出选中项")

        layout.addLayout(source_file_layout)
        layout.addLayout(analysis_controls_layout)
        layout.addLayout(results_controls_layout)
        layout.addWidget(self.similar_results_table)
        layout.addWidget(self.export_similar_button)
        group_box.setLayout(layout)
        return group_box

    def _connect_signals(self):
        """连接内部 UI 事件到外部信号。"""
        self.select_cluster_target_dir_button.clicked.connect(self._on_select_cluster_target_dir)
        self.run_kmeans_button.clicked.connect(self._on_run_kmeans)
        self.run_similarity_button.clicked.connect(self._on_run_similarity)
        
        self.select_source_file_button.clicked.connect(self.select_source_file_clicked.emit)
        self.find_similar_button.clicked.connect(self._on_find_similar)
        self.export_similar_button.clicked.connect(self._on_export_similar)
        self.select_all_similar_checkbox.stateChanged.connect(self._on_select_all_similar_changed)

    def _on_select_cluster_target_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择聚类目标文件夹")
        if directory:
            # 关键修复：立即将路径转换为原生格式
            native_path = os.path.normpath(directory)
            self.set_cluster_target_dir(native_path)

    def _on_run_kmeans(self):
        if self.cluster_target_dir:
            k = self.k_spinbox.value()
            self.run_kmeans_clicked.emit(self.cluster_target_dir, k)

    def _on_run_similarity(self):
        if self.cluster_target_dir:
            threshold = self.similarity_threshold_spinbox.value()
            self.run_similarity_clicked.emit(self.cluster_target_dir, threshold)

    def _on_find_similar(self):
        if self.source_file_id != -1:
            top_n = self.top_n_spinbox.value()
            self.find_similar_clicked.emit(self.source_file_id, top_n)

    def _on_export_similar(self):
        selected_ids = self.get_selected_similar_doc_ids()
        if selected_ids and self.source_file_path:
            self.export_similar_clicked.emit(selected_ids, self.source_file_path)

    def _on_select_all_similar_changed(self, state: int):
        check_state = Qt.CheckState(state)
        for row in range(self.similar_results_table.rowCount()):
            item = self.similar_results_table.item(row, 0)
            if item:
                item.setCheckState(check_state)

    # --- 公共接口 ---

    def set_cluster_target_dir(self, path: str):
        # 确保传入的任何路径都被规范化
        native_path = os.path.normpath(path) if path else ""
        self.cluster_target_dir = native_path
        self.cluster_target_dir_line_edit.setText(native_path)

    def set_source_file(self, path: str, file_id: int):
        # 确保传入的任何路径都被规范化
        native_path = os.path.normpath(path) if path else ""
        self.source_file_path = native_path
        self.source_file_id = file_id
        self.source_file_line_edit.setText(native_path)

    def display_similar_results(self, results: List[Dict[str, Any]]):
        self.similar_results_table.setRowCount(0)
        if not results: return

        self.similar_results_table.setRowCount(len(results))
        for row, item_data in enumerate(results):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            
            # 确保显示的路径也是原生格式
            native_path = os.path.normpath(item_data["path"])
            path_item = QTableWidgetItem(native_path)
            score_item = QTableWidgetItem(f"{item_data['score']:.4f}")

            path_item.setData(Qt.ItemDataRole.UserRole, item_data["id"])

            self.similar_results_table.setItem(row, 0, checkbox_item)
            self.similar_results_table.setItem(row, 1, path_item)
            self.similar_results_table.setItem(row, 2, score_item)

    def get_selected_similar_doc_ids(self) -> List[int]:
        selected_ids = []
        for row in range(self.similar_results_table.rowCount()):
            if self.similar_results_table.item(row, 0).checkState() == Qt.CheckState.Checked:
                selected_ids.append(self.similar_results_table.item(row, 1).data(Qt.ItemDataRole.UserRole))
        return selected_ids
