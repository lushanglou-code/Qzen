# -*- coding: utf-8 -*-
"""
单元测试模块：测试业务流程协调器 Orchestrator (v5.4)。

此测试套件通过模拟 (Mocking) 外部依赖，专注于验证 Orchestrator 的核心业务逻辑，
包括数据摄取流程中的“扁平化、去重与重命名”策略，以及与各个服务之间的交互是否正确。
"""

import os
import unittest
from unittest.mock import MagicMock, patch, call, ANY

# 将项目根目录添加到sys.path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qzen_core.orchestrator import Orchestrator, _vector_to_json
from qzen_data.models import Document, DeduplicationResult, TaskRun
from scipy.sparse import csr_matrix, vstack
import numpy as np


class TestOrchestrator(unittest.TestCase):
    """测试 Orchestrator 类的功能。"""

    def setUp(self):
        self.mock_db_handler = MagicMock()
        self.orchestrator = Orchestrator(db_handler=self.mock_db_handler, max_features=5000, slice_size_kb=1)
        self.orchestrator.similarity_engine = MagicMock()
        self.orchestrator.cluster_engine = MagicMock()

    def test_instantiation(self):
        self.assertIsNotNone(self.orchestrator)
        self.assertEqual(self.orchestrator.db_handler, self.mock_db_handler)

    @patch('qzen_core.orchestrator.file_handler')
    @patch('qzen_core.orchestrator.shutil')
    @patch('qzen_core.orchestrator.os')
    def test_deduplication_flattens_and_renames_on_conflict(self, mock_os, mock_shutil, mock_file_handler):
        """
        验证: run_deduplication_core 是否正确地实现了“扁平化、去重与重命名”策略。
        """
        # --- Arrange ---
        source_path = "/source"
        intermediate_path = "/intermediate"
        allowed_extensions = {'.txt'}

        # 1. 模拟文件系统扫描结果：两个内容不同但同名的文件，位于不同子目录
        file1_original_path = os.path.join(source_path, "A", "report.txt")
        file2_original_path = os.path.join(source_path, "B", "report.txt")
        file3_duplicate_content_path = os.path.join(source_path, "C", "report.txt") # 内容与 file1 相同

        mock_file_handler.scan_files.return_value = [file1_original_path, file2_original_path, file3_duplicate_content_path]

        # 2. 模拟内容切片和哈希计算
        def get_slice_side_effect(path):
            if path == file1_original_path: return "content1"
            if path == file2_original_path: return "content2"
            if path == file3_duplicate_content_path: return "content1" # 与 file1 内容相同
            return ""
        def get_hash_side_effect(content):
            if content == "content1": return "hash1"
            if content == "content2": return "hash2"
            return ""
        mock_file_handler.get_content_slice.side_effect = get_slice_side_effect
        mock_file_handler.calculate_content_hash.side_effect = get_hash_side_effect

        # 3. 模拟 os 行为以触发重命名
        mock_os.path.join.side_effect = os.path.join
        mock_os.path.basename.side_effect = os.path.basename
        mock_os.path.splitext.side_effect = os.path.splitext
        mock_os.path.split.side_effect = os.path.split

        # 关键：模拟 os.path.exists 来触发重命名逻辑
        mock_os.path.exists.side_effect = [False, True, False]

        # 4. 模拟数据库任务创建
        self.mock_db_handler.create_task_run.return_value = TaskRun(id=1)

        # --- Act ---
        summary, results = self.orchestrator.run_deduplication_core(
            source_path, intermediate_path, allowed_extensions, MagicMock(), lambda: False
        )

        # --- Assert ---
        # 1. 断言内容去重：只处理了两个唯一内容的文件
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].duplicate_file_path, file3_duplicate_content_path)

        # 2. 断言扁平化与重命名：shutil.copy2 被调用了两次，且第二次的目标路径被重命名
        self.assertEqual(mock_shutil.copy2.call_count, 2)
        expected_copy_calls = [
            call(file1_original_path, os.path.join(intermediate_path, "report.txt")),
            call(file2_original_path, os.path.join(intermediate_path, "report_dup1.txt"))
        ]
        mock_shutil.copy2.assert_has_calls(expected_copy_calls, any_order=False)

        # 3. 断言数据库记录的正确性：存入数据库的路径是经过重命名后的权威路径
        self.mock_db_handler.bulk_insert_documents.assert_called_once()
        docs_to_save = self.mock_db_handler.bulk_insert_documents.call_args[0][0]
        self.assertEqual(len(docs_to_save), 2)

        saved_paths = {doc.file_path for doc in docs_to_save}
        expected_paths_in_db = {
            os.path.join(intermediate_path, "report.txt").replace('\\', '/'),
            os.path.join(intermediate_path, "report_dup1.txt").replace('\\', '/')
        }
        self.assertSetEqual(saved_paths, expected_paths_in_db)

    @patch('qzen_core.orchestrator.file_handler')
    @patch('qzen_core.orchestrator.shutil')
    def test_run_deduplication_core_cancellation(self, mock_shutil, mock_file_handler):
        mock_file_handler.scan_files.return_value = ["/source/file1.txt"]
        self.mock_db_handler.create_task_run.return_value = TaskRun(id=1)
        summary, results = self.orchestrator.run_deduplication_core("/source", "/intermediate", {'.txt'}, MagicMock(), lambda: True)
        self.assertEqual(summary, "任务已取消")
        mock_shutil.copy2.assert_not_called()
        self.mock_db_handler.bulk_insert_documents.assert_not_called()

    def test_run_vectorization_happy_path(self):
        doc1, doc2 = Document(file_path="/path/doc1.txt", content_slice="content1"), Document(file_path="/path/doc2.txt", content_slice="content2")
        self.mock_db_handler.get_documents_without_vectors.return_value = [doc1, doc2]
        mock_feature_matrix = csr_matrix(np.array([[1, 2, 0], [0, 3, 4]]))
        self.orchestrator.similarity_engine.vectorize_documents.return_value = mock_feature_matrix
        result_summary = self.orchestrator.run_vectorization(MagicMock(), MagicMock(return_value=False))
        self.mock_db_handler.get_documents_without_vectors.assert_called_once()
        self.orchestrator.similarity_engine.vectorize_documents.assert_called_once_with(["content1", "content2"])
        self.mock_db_handler.bulk_update_documents.assert_called_once()
        updated_docs = self.mock_db_handler.bulk_update_documents.call_args[0][0]
        self.assertEqual(updated_docs[0].feature_vector, _vector_to_json(mock_feature_matrix[0]))

    def test_run_vectorization_no_docs_to_process(self):
        self.mock_db_handler.get_documents_without_vectors.return_value = []
        result_summary = self.orchestrator.run_vectorization(MagicMock(), MagicMock(return_value=False))
        self.mock_db_handler.get_documents_without_vectors.assert_called_once()
        self.orchestrator.similarity_engine.vectorize_documents.assert_not_called()
        self.assertIn("无需操作", result_summary)

    def test_prime_similarity_engine_happy_path(self):
        vec1, vec2 = csr_matrix(np.array([[1, 0, 1]])), csr_matrix(np.array([[0, 1, 1]]))
        doc1 = Document(id=1, file_path="/path/doc1.txt", feature_vector=_vector_to_json(vec1))
        doc2 = Document(id=2, file_path="/path/doc2.txt", feature_vector=_vector_to_json(vec2))
        doc3 = Document(id=3, file_path="/path/doc3.txt", feature_vector=None)
        self.mock_db_handler.get_all_documents.return_value = [doc1, doc2, doc3]
        
        self.orchestrator.prime_similarity_engine()
        
        self.mock_db_handler.get_all_documents.assert_called_once()
        
        expected_matrix = vstack([vec1, vec2])
        expected_doc_map = [
            {'id': 1, 'file_path': '/path/doc1.txt'},
            {'id': 2, 'file_path': '/path/doc2.txt'}
        ]
        
        self.assertTrue(np.array_equal(self.orchestrator.similarity_engine.feature_matrix.toarray(), expected_matrix.toarray()))
        self.assertEqual(self.orchestrator.similarity_engine.doc_map, expected_doc_map)
        self.assertTrue(self.orchestrator._is_engine_primed)

    def test_prime_similarity_engine_no_vectors(self):
        self.mock_db_handler.get_all_documents.return_value = [Document(file_path="/path/doc1.txt", feature_vector=None)]
        
        self.orchestrator.prime_similarity_engine()
        
        self.assertIsNone(self.orchestrator.similarity_engine.feature_matrix)
        self.assertEqual(self.orchestrator.similarity_engine.doc_map, [])
        self.assertTrue(self.orchestrator._is_engine_primed)

    @patch('qzen_core.orchestrator.logging')
    def test_prime_similarity_engine_invalid_json(self, mock_logging):
        vec1 = csr_matrix(np.array([[1, 0, 1]]))
        doc1 = Document(file_path="/path/doc1.txt", feature_vector=_vector_to_json(vec1))
        doc2 = Document(file_path="/path/doc2.txt", feature_vector="invalid-json")
        self.mock_db_handler.get_all_documents.return_value = [doc1, doc2]
        
        self.orchestrator.prime_similarity_engine()
        
        mock_logging.error.assert_called_once()

if __name__ == '__main__':
    unittest.main()
