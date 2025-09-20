# -*- coding: utf-8 -*-
"""
UI 模块：关键词搜索标签页 (v3.1 - 增加复选框选择)。

此版本根据用户建议，将结果列表从 QListWidget 升级为 QTableWidget，
并增加了行首复选框和“全选/全不选”功能，极大地优化了导出体验。
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from typing import List

from qzen_data.models import Document # 引入 Document 以便进行类型提示

class KeywordSearchTab(QWidget):
    """
    封装了“关键词搜索”标签页的所有 UI 控件和布局。
    """
    search_by_filename_clicked = pyqtSignal(str)
    search_by_content_clicked = pyqtSignal(str)
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

        # --- 结果展示与导出区 (v3.1 重构) ---
        results_layout = QHBoxLayout()
        self.select_all_checkbox = QCheckBox("全选/全不选")
        results_layout.addWidget(self.select_all_checkbox)
        results_layout.addStretch()
        layout.addLayout(results_layout)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(2)
        self.results_table.setHorizontalHeaderLabels(["选择", "文件路径"])
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setColumnWidth(0, 50)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.results_table)

        self.export_button = QPushButton("导出选中结果到目标文件夹")
        layout.addWidget(self.export_button)

    def _connect_signals(self):
        """连接内部 UI 事件到外部信号。"""
        self.filename_search_button.clicked.connect(self._on_search_filename)
        self.content_search_button.clicked.connect(self._on_search_content)
        self.export_button.clicked.connect(self._on_export)
        self.select_all_checkbox.stateChanged.connect(self._on_select_all_changed)

    def _on_search_filename(self):
        keyword = self.get_keyword()
        if keyword:
            self.search_by_filename_clicked.emit(keyword)

    def _on_search_content(self):
        keyword = self.get_keyword()
        if keyword:
            self.search_by_content_clicked.emit(keyword)

    def _on_export(self):
        selected_ids = self.get_selected_doc_ids()
        keyword = self.get_keyword()
        if selected_ids and keyword:
            self.export_results_clicked.emit(selected_ids, keyword)

    def _on_select_all_changed(self, state: int):
        """当“全选”复选框状态改变时，同步所有行的复选框。"""
        check_state = Qt.CheckState(state)
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 0)
            if item:
                item.setCheckState(check_state)

    # --- 公共接口 ---

    def get_keyword(self) -> str:
        """获取当前输入的关键词。"""
        return self.keyword_input.text().strip()

    def get_selected_doc_ids(self) -> List[int]:
        """遍历表格，获取所有被勾选的项的文档 ID。"""
        selected_ids = []
        for row in range(self.results_table.rowCount()):
            checkbox_item = self.results_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.CheckState.Checked:
                path_item = self.results_table.item(row, 1)
                if path_item:
                    selected_ids.append(path_item.data(Qt.ItemDataRole.UserRole))
        return selected_ids

    def display_results(self, documents: List[Document]):
        """在表格中显示搜索结果，并为每一行添加复选框。"""
        self.results_table.setRowCount(0)
        if not documents:
            # 可以在这里显示一个提示，或者保持表格为空
            return

        self.results_table.setRowCount(len(documents))
        for row, doc in enumerate(documents):
            # 创建复选框单元格
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.results_table.setItem(row, 0, checkbox_item)

            # 创建文件路径单元格
            path_item = QTableWidgetItem(doc.file_path)
            path_item.setData(Qt.ItemDataRole.UserRole, doc.id) # 将 doc.id 存入文件路径单元格
            self.results_table.setItem(row, 1, path_item)

    def set_config(self, config: dict):
        """加载配置（例如上次的关键词）。"""
        self.keyword_input.setText(config.get("last_keyword", ""))
