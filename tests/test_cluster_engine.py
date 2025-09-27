# -*- coding: utf-8 -*-
"""
测试单元：文件聚类引擎 (v5.5)

此测试验证 ClusterEngine 的核心功能，并与 v5.5 版本的代码保持同步：
1.  相似度聚类能否正确识别“相似文件簇”和“独立文件”，并将它们移动到
    更新后的目录结构中（`similar_clusters` 和 `unclustered`）。
2.  空目录清理逻辑的正确性。
"""

import unittest
import os
import shutil
from unittest.mock import Mock, patch, call

from qzen_core.cluster_engine import ClusterEngine
from qzen_data.models import Document
import numpy as np


class TestClusterEngine(unittest.TestCase):
    """
    测试 ClusterEngine 的功能。
    """

    def setUp(self):
        """在每个测试前，设置模拟依赖项和临时目录。"""
        self.mock_db_handler = Mock()
        self.mock_sim_engine = Mock()
        self.engine = ClusterEngine(self.mock_db_handler, self.mock_sim_engine)

        # 为文件系统测试设置临时目录
        self.test_root = "temp_test_dir_for_cleanup"
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)
        os.makedirs(self.test_root)

    def tearDown(self):
        """在每个测试后，清理临时目录。"""
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)

    @patch('qzen_core.cluster_engine.ClusterEngine._sanitize_filename', side_effect=lambda x: x)
    @patch('qzen_core.cluster_engine.cosine_similarity')
    @patch('qzen_core.cluster_engine.ClusterEngine._move_files_to_cluster_dir')
    @patch('qzen_core.cluster_engine.ClusterEngine._get_top_keywords', return_value="mock_keywords")
    def test_run_similarity_clustering_moves_alone_files(self, mock_get_keywords, mock_move_files, mock_cosine_similarity, mock_sanitize):
        """
        v5.5 验证: 测试 run_similarity_clustering 是否能正确处理相似文件和独立文件，
        并使用新的目录结构 'similar_clusters' 和 'unclustered'。
        """
        # --- Arrange ---
        target_dir = "/target"
        threshold = 0.8

        # 1. 模拟文档数据：2个相似，2个独立
        doc1_sim = Document(id=1, file_path="/path/sim1.txt")
        doc2_sim = Document(id=2, file_path="/path/sim2.txt")
        doc3_alone = Document(id=3, file_path="/path/alone1.txt")
        doc4_alone = Document(id=4, file_path="/path/alone2.txt")
        all_docs = [doc1_sim, doc2_sim, doc3_alone, doc4_alone]

        # 2. 模拟引擎和数据库返回的数据
        self.engine._get_docs_in_dir = Mock(return_value=all_docs)
        self.mock_db_handler.get_documents_by_ids.side_effect = lambda ids: [d for d in all_docs if d.id in ids]
        self.mock_sim_engine.doc_map = [
            {'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}
        ]
        self.mock_sim_engine.feature_matrix = np.array([[1,1,0,0], [1,1,0,0], [0,0,1,1], [0,0,0,1]]) # Mock matrix

        # 3. 模拟相似度矩阵，让 doc1 和 doc2 相似
        mock_cosine_similarity.return_value = np.array([
            [1.0, 0.9, 0.1, 0.2],  # doc1
            [0.9, 1.0, 0.3, 0.4],  # doc2
            [0.1, 0.3, 1.0, 0.5],  # doc3
            [0.2, 0.4, 0.5, 1.0],  # doc4
        ])

        # --- Act ---
        self.engine.run_similarity_clustering(target_dir, threshold, Mock(), lambda: False)

        # --- Assert ---
        # 1. 验证 _move_files_to_cluster_dir 被调用了两次
        self.assertEqual(mock_move_files.call_count, 2, "移动方法应被调用两次：一次为相似簇，一次为独立文件")

        # 2. v5.5 验证: 对“similar_clusters”的调用是正确的
        call_for_similar = call(
            [doc1_sim, doc2_sim],                # 移动的文档
            os.path.join(target_dir, "similar_clusters"), # v5.5 新的基础目录
            "00_mock_keywords",                  # v5.5 新的簇名称 (无父目录前缀)
            unittest.mock.ANY,                   # progress_callback
            unittest.mock.ANY                    # is_cancelled_callback
        )

        # 3. v5.5 验证: 对“unclustered”文件夹的调用是正确的
        call_for_unclustered = call(
            [doc3_alone, doc4_alone],            # 移动的文档
            target_dir,                          # 基础目录
            "unclustered",                       # v5.5 新的簇名称
            unittest.mock.ANY,                   # progress_callback
            unittest.mock.ANY                    # is_cancelled_callback
        )

        # 4. 使用 assert_has_calls 验证两次调用都发生了，不关心顺序
        mock_move_files.assert_has_calls([call_for_similar, call_for_unclustered], any_order=True)


    def test_cleanup_empty_folders(self):
        """
        测试 _cleanup_empty_folders 是否能正确删除空目录，保留非空目录。
        (此测试逻辑继承自旧版本，并更新了方法名)
        """
        # --- Arrange ---
        # 创建一个复杂的目录结构
        empty_child = os.path.join(self.test_root, "empty_parent", "empty_child")
        not_empty_dir = os.path.join(self.test_root, "not_empty")
        file_in_not_empty = os.path.join(not_empty_dir, "file.txt")
        empty_sibling = os.path.join(self.test_root, "empty_sibling")

        os.makedirs(empty_child)
        os.makedirs(not_empty_dir)
        os.makedirs(empty_sibling)
        with open(file_in_not_empty, "w") as f:
            f.write("hello")

        # --- Act ---
        # 调用被测试的私有方法
        self.engine._cleanup_empty_folders(self.test_root)

        # --- Assert ---
        self.assertFalse(os.path.exists(empty_child), "空的子目录应该被删除")
        self.assertFalse(os.path.exists(os.path.dirname(empty_child)), "空的父目录应该被删除")
        self.assertFalse(os.path.exists(empty_sibling), "空的同级目录应该被删除")
        self.assertTrue(os.path.exists(not_empty_dir), "非空目录不应该被删除")
        self.assertTrue(os.path.exists(file_in_not_empty), "目录中的文件不应该被删除")


if __name__ == '__main__':
    unittest.main()
