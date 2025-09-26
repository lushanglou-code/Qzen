# -*- coding: utf-8 -*-
"""
测试单元：分析与聚类标签页 (v5.4.2)。

此版本修复了信号发射测试。之前的测试直接调用了 `set_cluster_target_dir`，
而更健壮的测试应该模拟用户的完整交互。新的测试通过模拟 QFileDialog 
和按钮点击，来确保从选择文件夹到执行聚类的整个流程都能正确触发信号。
"""

import os
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication

from qzen_ui.tabs.analysis_cluster_tab import AnalysisClusterTab

# QApplication 的实例对于任何 Qt 测试都是必需的
app = QApplication([])

class TestAnalysisClusterTab(unittest.TestCase):
    """
    测试 AnalysisClusterTab 的 UI 交互和信号发射。
    """

    def setUp(self):
        """在每个测试方法运行前，创建一个新的标签页实例。"""
        self.tab = AnalysisClusterTab()

    @patch('PyQt6.QtWidgets.QFileDialog.getExistingDirectory')
    def test_run_kmeans_signal_emitted_correctly(self, mock_get_dir):
        """
        测试: 模拟用户选择文件夹、设置参数并点击 K-Means 按钮的完整流程。
        """
        # 1. 模拟用户选择文件夹
        test_directory = "/path/to/test/dir"
        mock_get_dir.return_value = test_directory
        self.tab.select_cluster_target_dir_button.click()

        # 2. 模拟用户设置 K 值
        test_k = 7
        self.tab.k_spinbox.setValue(test_k)

        # 3. 连接信号到 spy
        spy_slot = Mock()
        self.tab.run_kmeans_clicked.connect(spy_slot)

        # 4. 模拟用户点击按钮
        self.tab.run_kmeans_button.click()

        # 5. 断言信号被正确发射
        expected_path = os.path.normpath(test_directory)
        spy_slot.assert_called_once_with(expected_path, test_k)

    @patch('PyQt6.QtWidgets.QFileDialog.getExistingDirectory')
    def test_run_similarity_signal_emitted_correctly(self, mock_get_dir):
        """
        测试: 模拟用户选择文件夹、设置参数并点击相似度分组按钮的完整流程。
        """
        test_directory = "/path/to/test/dir"
        mock_get_dir.return_value = test_directory
        self.tab.select_cluster_target_dir_button.click()

        test_threshold = 0.9
        self.tab.similarity_threshold_spinbox.setValue(test_threshold)

        spy_slot = Mock()
        self.tab.run_similarity_clicked.connect(spy_slot)

        self.tab.run_similarity_button.click()

        expected_path = os.path.normpath(test_directory)
        spy_slot.assert_called_once_with(expected_path, test_threshold)

    def test_signals_not_emitted_if_dir_is_empty(self):
        """
        测试边界条件：如果目标目录为空，则点击任一聚类按钮都不应发射信号。
        """
        self.tab.set_cluster_target_dir("")

        kmeans_spy = Mock()
        similarity_spy = Mock()
        self.tab.run_kmeans_clicked.connect(kmeans_spy)
        self.tab.run_similarity_clicked.connect(similarity_spy)

        self.tab.run_kmeans_button.click()
        self.tab.run_similarity_button.click()

        kmeans_spy.assert_not_called()
        similarity_spy.assert_not_called()

    @patch('PyQt6.QtWidgets.QFileDialog.getExistingDirectory')
    def test_select_directory_button_updates_path(self, mock_get_dir):
        """
        测试文件夹选择按钮是否能正确更新 UI 上的路径，并处理路径规范化。
        """
        test_path = "/selected/from/dialog"
        mock_get_dir.return_value = test_path
        
        expected_path = os.path.normpath(test_path)

        self.tab.select_cluster_target_dir_button.click()

        self.assertEqual(self.tab.cluster_target_dir_line_edit.text(), expected_path)
        self.assertEqual(self.tab.cluster_target_dir, expected_path)

if __name__ == '__main__':
    unittest.main()
