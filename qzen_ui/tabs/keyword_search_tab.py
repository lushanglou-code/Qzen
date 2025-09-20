# -*- coding: utf-8 -*-
"""
UI 模块：关键词搜索标签页 (v2.1 修正版)

此版本已重构，统一使用数据库自增 ID (doc_id) 作为文档的唯一标识符。
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import pyqtSignal, Qt
from typing import List

from qzen_data.models import Document # 引入 Document 以便进行类型提示

class KeywordSearchTab(QWidget):
    """
    封装了“关键词搜索”标签页的所有 UI 控件和布局。
    """
    # 定义信号
    search_by_filename_clicked = pyqtSignal(str)
    search_by_content_clicked = pyqtSignal(str)
    # 修正: 信号现在传递一个整数列表 (doc_ids)
    export_results_clicked = pyqtSignal(list, str) # doc_ids: List[int], keyword: str

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """创建并布局所有 UI 控件。"""
        layout = QVBoxLayout(self)

        # --- 输入区 ---
        input_layout = QHBoxLayout()
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("在此输入关键词...")
        input_layout.addWidget(QLabel("关键词:"))
        input_layout.addWidget(self.keyword_input)
        layout.addLayout(input_layout)

        # --- 搜索按钮区 ---
        search_button_layout = QHBoxLayout()
        self.filename_search_button = QPushButton("按文件名搜索")
        self.content_search_button = QPushButton("按文件内容搜索")
        search_button_layout.addWidget(self.filename_search_button)
        search_button_layout.addWidget(self.content_search_button)
        search_button_layout.addStretch()
        layout.addLayout(search_button_layout)

        # --- 结果展示与导出区 ---
        layout.addWidget(QLabel("搜索结果:"))
        self.results_list = QListWidget()
        self.results_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.results_list)

        self.export_button = QPushButton("导出选中结果到目标文件夹")
        layout.addWidget(self.export_button)

    def _connect_signals(self):
        """连接内部 UI 事件到外部信号。"""
        self.filename_search_button.clicked.connect(self._on_search_filename)
        self.content_search_button.clicked.connect(self._on_search_content)
        self.export_button.clicked.connect(self._on_export)

    def _on_search_filename(self):
        keyword = self.get_keyword()
        if keyword:
            self.search_by_filename_clicked.emit(keyword)

    def _on_search_content(self):
        keyword = self.get_keyword()
        if keyword:
            self.search_by_content_clicked.emit(keyword)

    def _on_export(self):
        # 修正: 获取并传递 doc_ids 列表
        selected_ids = self.get_selected_doc_ids()
        keyword = self.get_keyword()
        if selected_ids and keyword:
            self.export_results_clicked.emit(selected_ids, keyword)

    # --- 公共接口 ---

    def get_keyword(self) -> str:
        """获取当前输入的关键词。"""
        return self.keyword_input.text().strip()

    def get_selected_doc_ids(self) -> List[int]:
        """获取结果列表中所有被选中的项的文档 ID。"""
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.results_list.selectedItems()]

    def display_results(self, documents: List[Document]):
        """在列表中显示搜索结果。"""
        self.results_list.clear()
        if not documents:
            self.results_list.addItem("没有找到匹配的结果。")
            return
        
        for doc in documents:
            # 修正: 存储 doc.id 而不是 doc.file_hash
            item = QListWidgetItem(f"{doc.file_path} (ID: {doc.id})")
            item.setData(Qt.ItemDataRole.UserRole, doc.id)
            self.results_list.addItem(item)

    def set_config(self, config: dict):
        """加载配置（例如上次的关键词）。"""
        self.keyword_input.setText(config.get("last_keyword", ""))
