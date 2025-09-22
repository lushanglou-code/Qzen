# -*- coding: utf-8 -*-
"""
测试单元：分析与聚类标签页 (v3.2 修正版)。

此测试验证 AnalysisClusterTab 的核心交互逻辑，确保在移除目录树后，
通过文件夹选择对话框驱动的聚类流程能正确触发信号。
"""

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

    def test_run_clustering_signal_emitted_with_correct_data(self):
        """
        测试核心功能：当用户设置了目标目录并点击“运行聚类”时，
        是否能以正确的参数发射 run_clustering_clicked 信号。
        """
        # 1. 模拟用户设置的目标目录、K值和阈值
        test_directory = "/path/to/test/dir"
        test_k = 7
        test_threshold = 0.9

        # v3.2 修正: 调用更新后的方法名
        self.tab.set_cluster_target_dir(test_directory)
        self.tab.k_spinbox.setValue(test_k)
        self.tab.similarity_threshold_spinbox.setValue(test_threshold)

        # 2. 创建一个“间谍”函数来监听信号
        spy_slot = Mock()
        self.tab.run_clustering_clicked.connect(spy_slot)

        # 3. 模拟用户点击“运行聚类”按钮
        self.tab.run_clustering_button.click()

        # 4. 断言：“间谍”函数被调用了一次，并且接收到的参数与我们设置的完全一致
        spy_slot.assert_called_once_with(test_directory, test_k, test_threshold)

    def test_run_clustering_signal_not_emitted_if_dir_is_empty(self):
        """
        测试边界条件：如果目标目录为空，则不应发射信号。
        """
        # 1. 确保目标目录为空
        # v3.2 修正: 调用更新后的方法名
        self.tab.set_cluster_target_dir("")

        # 2. 创建一个“间谍”函数
        spy_slot = Mock()
        self.tab.run_clustering_clicked.connect(spy_slot)

        # 3. 模拟点击
        self.tab.run_clustering_button.click()

        # 4. 断言：“间谍”函数从未被调用
        spy_slot.assert_not_called()

    @patch('PyQt6.QtWidgets.QFileDialog.getExistingDirectory')
    def test_select_directory_button_updates_path(self, mock_get_dir):
        """
        测试文件夹选择按钮是否能正确更新 UI 上的路径。
        """
        # 1. 配置模拟的 QFileDialog，使其“返回”一个指定的路径
        test_path = "/selected/from/dialog"
        mock_get_dir.return_value = test_path

        # 2. 模拟用户点击“选择文件夹”按钮
        # v3.2 修正: 调用更新后的按钮名
        self.tab.select_cluster_target_dir_button.click()

        # 3. 断言：QLineEdit 中的文本已被更新为对话框返回的路径
        # v3.2 修正: 检查更新后的控件和属性名
        self.assertEqual(self.tab.cluster_target_dir_line_edit.text(), test_path)
        self.assertEqual(self.tab.cluster_target_dir, test_path)

if __name__ == '__main__':
    unittest.main()
