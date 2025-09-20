# -*- coding: utf-8 -*-
"""
测试单元：关键词搜索标签页 (v3.1)

此测试验证 KeywordSearchTab 的核心交互逻辑，特别是带有复选框和
“全选/全不选”功能的结果列表。
"""

import unittest
from unittest.mock import Mock

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from qzen_ui.tabs.keyword_search_tab import KeywordSearchTab
from qzen_data.models import Document

# QApplication 的实例对于任何 Qt 测试都是必需的
app = QApplication([])

class TestKeywordSearchTab(unittest.TestCase):
    """
    测试 KeywordSearchTab 的 UI 交互和信号发射。
    """

    def setUp(self):
        """在每个测试方法运行前，创建一个新的标签页实例和一些模拟数据。"""
        self.tab = KeywordSearchTab()
        # 创建一些模拟的 Document 对象
        self.mock_documents = [
            Document(id=101, file_path="/path/a.txt"),
            Document(id=202, file_path="/path/b.txt"),
            Document(id=303, file_path="/path/c.txt"),
        ]

    def test_display_results_populates_table_correctly(self):
        """
        测试 display_results 是否能正确地用复选框和文件路径填充表格。
        """
        self.tab.display_results(self.mock_documents)

        # 断言表格有正确的行数
        self.assertEqual(self.tab.results_table.rowCount(), 3)
        # 断言第一行的内容是正确的
        self.assertEqual(self.tab.results_table.item(0, 1).text(), "/path/a.txt")
        self.assertEqual(self.tab.results_table.item(0, 1).data(Qt.ItemDataRole.UserRole), 101)
        # 断言第一行的复选框存在且未被选中
        self.assertIsNotNone(self.tab.results_table.item(0, 0))
        self.assertEqual(self.tab.results_table.item(0, 0).checkState(), Qt.CheckState.Unchecked)

    def test_select_all_checkbox_toggles_all_rows(self):
        """
        测试“全选/全不选”复选框是否能正确地控制所有行的复选框状态。
        """
        self.tab.display_results(self.mock_documents)

        # 1. 模拟用户勾选“全选”
        self.tab.select_all_checkbox.setCheckState(Qt.CheckState.Checked)

        # 断言：所有行的复选框都应被选中
        for row in range(self.tab.results_table.rowCount()):
            self.assertEqual(self.tab.results_table.item(row, 0).checkState(), Qt.CheckState.Checked)

        # 2. 模拟用户取消勾选“全选”
        self.tab.select_all_checkbox.setCheckState(Qt.CheckState.Unchecked)

        # 断言：所有行的复选框都应被取消选中
        for row in range(self.tab.results_table.rowCount()):
            self.assertEqual(self.tab.results_table.item(row, 0).checkState(), Qt.CheckState.Unchecked)

    def test_get_selected_doc_ids_returns_correct_ids(self):
        """
        测试 get_selected_doc_ids 是否只返回被勾选的行的文档 ID。
        """
        self.tab.display_results(self.mock_documents)

        # 1. 手动勾选第一行和第三行
        self.tab.results_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        self.tab.results_table.item(2, 0).setCheckState(Qt.CheckState.Checked)

        # 2. 调用方法获取 ID
        selected_ids = self.tab.get_selected_doc_ids()

        # 3. 断言返回的 ID 列表是正确的
        self.assertEqual(selected_ids, [101, 303])

if __name__ == '__main__':
    unittest.main()
