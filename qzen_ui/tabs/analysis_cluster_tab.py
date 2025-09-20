# -*- coding: utf-8 -*-
"""
UI 模块：分析与聚类标签页 (v3.0 - 终极稳定版)。

此版本根据最终用户建议，彻底移除了导致崩溃的 QTreeView 控件，
用一个标准的文件夹选择对话框替代，从根本上保证了 UI 的稳定性。
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, 
    QSpinBox, QDoubleSpinBox, QLineEdit, QFileDialog
)
from PyQt6.QtCore import pyqtSignal

class AnalysisClusterTab(QWidget):
    """
    封装了“分析与聚类”标签页的所有 UI 控件和布局。
    """
    run_clustering_clicked = pyqtSignal(str, int, float) # target_dir, k, threshold

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_dir = ""
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """创建并布局所有 UI 控件。"""
        main_layout = QVBoxLayout(self)

        # --- 目标文件夹选择区 ---
        target_dir_layout = QHBoxLayout()
        target_dir_layout.addWidget(QLabel("聚类目标文件夹:"))
        self.target_dir_line_edit = QLineEdit()
        self.target_dir_line_edit.setPlaceholderText("请点击右侧按钮选择一个文件夹作为聚类目标...")
        self.target_dir_line_edit.setReadOnly(True)
        self.select_target_dir_button = QPushButton("选择文件夹...")
        target_dir_layout.addWidget(self.target_dir_line_edit)
        target_dir_layout.addWidget(self.select_target_dir_button)

        # --- 聚类控制区 ---
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

        main_layout.addLayout(target_dir_layout)
        main_layout.addLayout(cluster_controls_layout)
        main_layout.addStretch() # 将所有控件推到顶部

    def _connect_signals(self):
        """连接内部 UI 事件到外部信号。"""
        self.select_target_dir_button.clicked.connect(self._on_select_target_dir)
        self.run_clustering_button.clicked.connect(self._on_run_clustering)

    def _on_select_target_dir(self):
        """打开文件夹选择对话框。"""
        directory = QFileDialog.getExistingDirectory(self, "选择聚类目标文件夹")
        if directory:
            self.set_target_dir(directory)

    def _on_run_clustering(self):
        """当聚类按钮被点击时，收集参数并发出信号。"""
        if self.target_dir:
            k = self.k_spinbox.value()
            threshold = self.similarity_threshold_spinbox.value()
            self.run_clustering_clicked.emit(self.target_dir, k, threshold)

    def set_target_dir(self, path: str):
        """由主窗口或自身调用，设置目标目录的显示路径。"""
        self.target_dir = path
        self.target_dir_line_edit.setText(path)
