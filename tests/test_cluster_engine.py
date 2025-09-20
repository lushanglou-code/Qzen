# -*- coding: utf-8 -*-
"""
测试单元：文件聚类引擎 (v3.0)

此测试验证 ClusterEngine 的核心功能，特别是新增的空目录清理逻辑。
"""

import unittest
import os
import shutil
from unittest.mock import Mock

from qzen_core.cluster_engine import ClusterEngine

class TestClusterEngine(unittest.TestCase):
    """
    测试 ClusterEngine 的功能，尤其是目录清理。
    """

    def setUp(self):
        """在每个测试前，创建一个临时的测试目录结构。"""
        self.test_root = "temp_test_dir"
        # 创建一个复杂的目录结构
        self.empty_child = os.path.join(self.test_root, "empty_parent", "empty_child")
        self.not_empty_dir = os.path.join(self.test_root, "not_empty")
        self.file_in_not_empty = os.path.join(self.not_empty_dir, "file.txt")
        self.empty_sibling = os.path.join(self.test_root, "empty_sibling")

        # 确保测试目录是干净的
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)

        os.makedirs(self.empty_child)
        os.makedirs(self.not_empty_dir)
        os.makedirs(self.empty_sibling)
        with open(self.file_in_not_empty, "w") as f:
            f.write("hello")

        # 模拟依赖项
        mock_db_handler = Mock()
        mock_sim_engine = Mock()
        self.engine = ClusterEngine(mock_db_handler, mock_sim_engine)

    def tearDown(self):
        """在每个测试后，清理临时目录。"""
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)

    def test_remove_empty_subdirectories(self):
        """
        测试核心功能：_remove_empty_subdirectories 是否能正确地
        删除所有空目录，同时保留非空目录。
        """
        # 调用被测试的私有方法
        self.engine._remove_empty_subdirectories(self.test_root)

        # --- 断言 ---
        # 1. 确认所有空目录都已被删除
        self.assertFalse(os.path.exists(self.empty_child), "空的子目录应该被删除")
        self.assertFalse(os.path.exists(os.path.dirname(self.empty_child)), "空的父目录应该被删除")
        self.assertFalse(os.path.exists(self.empty_sibling), "空的同级目录应该被删除")

        # 2. 确认所有非空目录和文件都得到保留
        self.assertTrue(os.path.exists(self.not_empty_dir), "非空目录不应该被删除")
        self.assertTrue(os.path.exists(self.file_in_not_empty), "目录中的文件不应该被删除")

if __name__ == '__main__':
    unittest.main()
