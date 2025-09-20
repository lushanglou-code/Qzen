# -*- coding: utf-8 -*-
"""
单元测试模块：测试数据摄取服务 (v2.1 修正版)。
"""

import unittest
import os
import shutil
from unittest.mock import MagicMock, patch, call, ANY

# 将项目根目录添加到sys.path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qzen_core.ingestion_service import IngestionService, _vector_to_json
from qzen_data.models import Document
from scipy.sparse import csr_matrix
import numpy as np


class TestIngestionService(unittest.TestCase):
    """测试 IngestionService 类的功能。"""

    def setUp(self):
        """为每个测试用例设置临时目录和模拟对象。"""
        self.test_dir = "temp_ingestion_test_dir"
        self.source_dir = os.path.join(self.test_dir, "source")
        self.intermediate_dir = os.path.join(self.test_dir, "intermediate")
        os.makedirs(self.source_dir, exist_ok=True)

        self.mock_db_handler = MagicMock()
        self.service = IngestionService(self.mock_db_handler)

    def tearDown(self):
        """在每个测试用例后清理临时目录。"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('qzen_core.ingestion_service.SimilarityEngine')
    @patch('qzen_core.ingestion_service.file_handler')
    @patch('qzen_core.ingestion_service.shutil')
    @patch('qzen_core.ingestion_service.os')
    def test_execute_full_workflow(self, mock_os, mock_shutil, mock_file_handler, MockSimilarityEngine):
        """测试 execute 方法是否能正确编排完整的端到端工作流。"""
        # --- Arrange ---
        # 1. 配置模拟的文件系统和路径操作
        mock_os.path.join.side_effect = os.path.join
        mock_os.path.normpath.side_effect = os.path.normpath
        mock_os.path.relpath.side_effect = os.path.relpath
        mock_os.path.dirname.return_value = self.intermediate_dir
        mock_os.path.basename.side_effect = os.path.basename
        mock_os.path.exists.return_value = False

        # 2. 准备模拟的源文件和内容
        mock_files_info = {
            "doc1.txt": ("hash1", "这是文档1的内容"),
            "doc2.pdf": ("hash2", "这是文档2的内容"),
            "doc1_duplicate.txt": ("hash1", "这是文档1的内容")
        }
        source_paths = [os.path.join(self.source_dir, name) for name in mock_files_info.keys()]
        
        # 3. 配置 file_handler 模拟
        mock_file_handler.scan_files.return_value = source_paths
        mock_file_handler.calculate_file_hash.side_effect = lambda fp: mock_files_info[os.path.basename(fp)][0]
        mock_file_handler.get_content_slice.side_effect = ["这是文档1的内容", "这是文档2的内容"]

        # 4. 配置 DB Handler 模拟
        doc1_intermediate_path = os.path.join(self.intermediate_dir, 'doc1.txt')
        doc2_intermediate_path = os.path.join(self.intermediate_dir, 'doc2.pdf')
        doc1 = Document(file_hash='hash1', file_path=doc1_intermediate_path)
        doc2 = Document(file_hash='hash2', file_path=doc2_intermediate_path)
        self.mock_db_handler.get_all_documents.return_value = [doc1, doc2]

        # 5. 配置 SimilarityEngine 模拟
        mock_sim_engine_instance = MockSimilarityEngine.return_value
        mock_feature_matrix = csr_matrix(np.array([[1, 2], [3, 4]]))
        mock_sim_engine_instance.vectorize_documents.return_value = mock_feature_matrix

        # --- Act ---
        result = self.service.execute(
            self.source_dir, self.intermediate_dir, custom_stopwords=['test'],
            progress_callback=MagicMock(), is_cancelled_callback=lambda: False
        )

        # --- Assert ---
        self.assertTrue(result, "工作流应该成功返回 True")

        # 验证工作空间准备
        self.mock_db_handler.recreate_tables.assert_called_once()
        # 修正: 使用 assert_any_call 验证对根目录的创建，忽略后续对子目录的创建
        mock_os.makedirs.assert_any_call(self.intermediate_dir)

        # 验证去重和复制 (保留原始文件名)
        mock_shutil.copy2.assert_has_calls([
            call(os.path.join(self.source_dir, 'doc1.txt'), doc1_intermediate_path),
            call(os.path.join(self.source_dir, 'doc2.pdf'), doc2_intermediate_path)
        ], any_order=True)
        self.assertEqual(mock_shutil.copy2.call_count, 2)

        # 验证数据库记录构建
        self.mock_db_handler.bulk_insert_documents.assert_called_once()
        inserted_docs = self.mock_db_handler.bulk_insert_documents.call_args[0][0]
        self.assertEqual(len(inserted_docs), 2)
        self.assertEqual({doc.file_hash for doc in inserted_docs}, {'hash1', 'hash2'})
        self.assertEqual({doc.file_path for doc in inserted_docs}, {doc1_intermediate_path, doc2_intermediate_path})

        # 验证内容提取和向量化
        self.mock_db_handler.get_all_documents.assert_called_once()
        MockSimilarityEngine.assert_called_once_with(custom_stopwords=['test'])
        mock_sim_engine_instance.vectorize_documents.assert_called_once_with(["这是文档1的内容", "这是文档2的内容"])
        
        # 验证最终的数据库更新
        self.mock_db_handler.bulk_update_documents.assert_called_once()
        updated_docs = self.mock_db_handler.bulk_update_documents.call_args[0][0]
        self.assertEqual(len(updated_docs), 2)
        self.assertEqual(updated_docs[0].content_slice, "这是文档1的内容")
        self.assertEqual(updated_docs[0].feature_vector, _vector_to_json(mock_feature_matrix[0]))
        self.assertEqual(updated_docs[1].content_slice, "这是文档2的内容")
        self.assertEqual(updated_docs[1].feature_vector, _vector_to_json(mock_feature_matrix[1]))

if __name__ == '__main__':
    unittest.main()
