# -*- coding: utf-8 -*-
"""
UI 模块：分析与聚类标签页 (v3.2 - 新增相似文件分析)。

此版本在保留了稳定的聚类功能的基础上，新增了“相似文件分析”
功能区，允许用户选择一个文件，查找并导出其最相似的文件。
"""

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
    # --- 聚类信号 ---
    run_clustering_clicked = pyqtSignal(str, int, float)
    
    # --- v3.2 新增：相似文件分析信号 ---
    select_source_file_clicked = pyqtSignal()
    find_similar_clicked = pyqtSignal(int, int) # source_file_id, top_n
    export_similar_clicked = pyqtSignal(list, str) # doc_ids, source_file_path

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

        # --- v3.2 功能区划分 ---
        main_layout.addWidget(self._create_clustering_group())
        main_layout.addWidget(self._create_similarity_group())
        main_layout.addStretch()

    def _create_clustering_group(self) -> QGroupBox:
        """创建聚类功能区。"""
        group_box = QGroupBox("多轮次聚类引擎")
        layout = QVBoxLayout()

        target_dir_layout = QHBoxLayout()
        target_dir_layout.addWidget(QLabel("聚类目标文件夹:"))
        self.cluster_target_dir_line_edit = QLineEdit()
        self.cluster_target_dir_line_edit.setPlaceholderText("请点击右侧按钮选择一个文件夹作为聚类目标...")
        self.cluster_target_dir_line_edit.setReadOnly(True)
        self.select_cluster_target_dir_button = QPushButton("选择文件夹...")
        target_dir_layout.addWidget(self.cluster_target_dir_line_edit)
        target_dir_layout.addWidget(self.select_cluster_target_dir_button)

        cluster_controls_layout = QHBoxLayout()
        cluster_controls_layout.addWidget(QLabel("K-Means K值:"))
        self.k_spinbox = QSpinBox()
        self.k_spinbox.setRange(2, 100)
        self.k_spinbox.setValue(5)
        cluster_controls_layout.addWidget(self.k_spinbox)
        cluster_controls_layout.addWidget(QLabel("相似度阈值:"))
        self.similarity_threshold_spinbox = QDoubleSpinBox()
        self.similarity_threshold_spinbox.setRange(0.1, 1.0)
        self.similarity_threshold_spinbox.setSingleStep(0.05)
        self.similarity_threshold_spinbox.setValue(0.85)
        cluster_controls_layout.addWidget(self.similarity_threshold_spinbox)
        self.run_clustering_button = QPushButton("对指定文件夹运行聚类")
        cluster_controls_layout.addWidget(self.run_clustering_button)
        cluster_controls_layout.addStretch()

        layout.addLayout(target_dir_layout)
        layout.addLayout(cluster_controls_layout)
        group_box.setLayout(layout)
        return group_box

    def _create_similarity_group(self) -> QGroupBox:
        """v3.2 新增: 创建相似文件分析功能区。"""
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
        self.run_clustering_button.clicked.connect(self._on_run_clustering)
        self.select_source_file_button.clicked.connect(self.select_source_file_clicked.emit)
        self.find_similar_button.clicked.connect(self._on_find_similar)
        self.export_similar_button.clicked.connect(self._on_export_similar)
        self.select_all_similar_checkbox.stateChanged.connect(self._on_select_all_similar_changed)

    def _on_select_cluster_target_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择聚类目标文件夹")
        if directory:
            self.set_cluster_target_dir(directory)

    def _on_run_clustering(self):
        if self.cluster_target_dir:
            k = self.k_spinbox.value()
            threshold = self.similarity_threshold_spinbox.value()
            self.run_clustering_clicked.emit(self.cluster_target_dir, k, threshold)

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
        self.cluster_target_dir = path
        self.cluster_target_dir_line_edit.setText(path)

    def set_source_file(self, path: str, file_id: int):
        self.source_file_path = path
        self.source_file_id = file_id
        self.source_file_line_edit.setText(path)

    def display_similar_results(self, results: List[Dict[str, Any]]):
        self.similar_results_table.setRowCount(0)
        if not results: return

        self.similar_results_table.setRowCount(len(results))
        for row, item_data in enumerate(results):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            
            path_item = QTableWidgetItem(item_data["path"])
            score_item = QTableWidgetItem(f"{item_data['score']:.4f}")

            # 将文档 ID 存入路径单元格以便导出
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
