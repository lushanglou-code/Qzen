# -*- coding: utf-8 -*-
"""
单元测试模块：测试数据摄取服务 (v5.4.2)。

此版本修复了 `test_execute_full_workflow` 中的一个断言错误。
该错误源于对 `os.path.exists` 的模拟过于简单，导致 `shutil.rmtree`
没有被按预期调用。新的模拟使用了 `side_effect` 来更精确地控制其行为。
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
        """v5.4.2 修复: 测试 execute 方法是否能正确编排完整的端到端工作流。"""
        # --- Arrange ---
        # 1. 配置路径模拟
        mock_os.path.join.side_effect = os.path.join
        mock_os.path.normpath.side_effect = os.path.normpath
        mock_os.path.relpath.side_effect = os.path.relpath
        mock_os.path.dirname.return_value = self.intermediate_dir
        mock_os.path.basename.side_effect = os.path.basename
        
        # v5.4.2 修复: 使用 side_effect 来智能地模拟 os.path.exists
        def mock_exists_side_effect(path):
            # 允许 rmtree 清理中间目录
            if path == self.intermediate_dir:
                return True
            # 假设所有目标文件路径都不存在，以避免触发重命名逻辑
            return False
        mock_os.path.exists.side_effect = mock_exists_side_effect

        # 2. 模拟源文件和内容摘要
        source_paths = [
            os.path.join(self.source_dir, "doc1.txt"),
            os.path.join(self.source_dir, "doc2.pdf"),
            os.path.join(self.source_dir, "doc1_duplicate.txt")
        ]
        content_slices = {source_paths[0]: "content_1", source_paths[1]: "content_2", source_paths[2]: "content_1"}
        slice_hashes = {"content_1": "hash1", "content_2": "hash2"}

        # 3. 配置 file_handler 模拟
        mock_file_handler.scan_files.return_value = source_paths
        mock_file_handler.get_content_slice.side_effect = lambda fp: content_slices.get(fp, "")
        mock_file_handler.calculate_content_hash.side_effect = lambda cs: slice_hashes.get(cs, "")

        # 4. 配置 DB Handler 模拟
        def mock_bulk_insert(docs):
            for i, doc in enumerate(docs):
                doc.id = i + 1
            return docs
        self.mock_db_handler.bulk_insert_documents.side_effect = mock_bulk_insert
        doc1 = Document(id=1, file_hash='hash1', file_path=os.path.join(self.intermediate_dir, 'doc1.txt'), content_slice='content_1')
        doc2 = Document(id=2, file_hash='hash2', file_path=os.path.join(self.intermediate_dir, 'doc2.pdf'), content_slice='content_2')
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
        mock_shutil.rmtree.assert_called_once_with(self.intermediate_dir)
        mock_os.makedirs.assert_any_call(self.intermediate_dir)

        # 验证去重和复制
        self.assertEqual(mock_shutil.copy2.call_count, 2)

        # 验证数据库记录构建
        self.mock_db_handler.bulk_insert_documents.assert_called_once()
        inserted_docs = self.mock_db_handler.bulk_insert_documents.call_args[0][0]
        self.assertEqual(len(inserted_docs), 2)
        self.assertEqual({doc.file_hash for doc in inserted_docs}, {'hash1', 'hash2'})

        # 验证向量化
        self.mock_db_handler.get_all_documents.assert_called_once()
        MockSimilarityEngine.assert_called_once_with(custom_stopwords=['test'])
        mock_sim_engine_instance.vectorize_documents.assert_called_once_with(['content_1', 'content_2'])
        
        # 验证最终的数据库更新
        self.mock_db_handler.bulk_update_documents.assert_called_once()
        updated_docs = self.mock_db_handler.bulk_update_documents.call_args[0][0]
        self.assertEqual(len(updated_docs), 2)
        self.assertEqual(updated_docs[0].feature_vector, _vector_to_json(mock_feature_matrix[0]))
        self.assertEqual(updated_docs[1].feature_vector, _vector_to_json(mock_feature_matrix[1]))

if __name__ == '__main__':
    unittest.main()
