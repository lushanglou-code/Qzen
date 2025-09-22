# -*- coding: utf-8 -*-
"""
单元测试模块：测试业务流程协调器 Orchestrator (v3.2 修正版)。

此版本更新了对 prime_similarity_engine 的测试，以匹配 v3.2 中
Orchestrator 和 SimilarityEngine 之间的新交互模式。
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
        # 注意：这里会创建一个真实的 Orchestrator，但我们随后会替换掉它的内部引擎
        self.orchestrator = Orchestrator(db_handler=self.mock_db_handler, max_features=5000, slice_size_kb=1)
        # 用模拟对象替换内部引擎，以便进行隔离测试
        self.orchestrator.similarity_engine = MagicMock()
        self.orchestrator.cluster_engine = MagicMock()

    def test_instantiation(self):
        self.assertIsNotNone(self.orchestrator)
        self.assertEqual(self.orchestrator.db_handler, self.mock_db_handler)

    @patch('qzen_core.orchestrator.Orchestrator.prime_similarity_engine')
    def test_run_iterative_clustering_delegates_to_cluster_engine(self, mock_prime_engine):
        """
        测试 run_iterative_clustering 是否正确地将调用委托给 ClusterEngine。
        """
        # --- Arrange ---
        target_dir = "/intermediate/folder_to_cluster"
        k = 5
        similarity_threshold = 0.85
        mock_progress_callback = MagicMock()
        mock_is_cancelled_callback = MagicMock(return_value=False)

        # 模拟引擎依赖项已准备就绪
        self.orchestrator.similarity_engine.feature_matrix = csr_matrix(np.eye(10))
        self.mock_db_handler.create_task_run.return_value = TaskRun(id=99)

        # --- Act ---
        summary = self.orchestrator.run_iterative_clustering(
            target_dir=target_dir,
            k=k,
            similarity_threshold=similarity_threshold,
            progress_callback=mock_progress_callback,
            is_cancelled_callback=mock_is_cancelled_callback
        )

        # --- Assert ---
        # 1. 验证 prime_similarity_engine 被调用以确保引擎已预热
        mock_prime_engine.assert_called_once_with(is_cancelled_callback=mock_is_cancelled_callback)

        # 2. 验证数据库任务已创建
        self.mock_db_handler.create_task_run.assert_called_once_with(task_type='iterative_clustering')

        # 3. 验证核心委托：Orchestrator 调用了 ClusterEngine 的 run_clustering 方法
        self.orchestrator.cluster_engine.run_clustering.assert_called_once_with(
            target_dir=target_dir,
            k=k,
            similarity_threshold=similarity_threshold,
            progress_callback=mock_progress_callback,
            is_cancelled_callback=mock_is_cancelled_callback
        )

        # 4. 验证任务摘要已更新
        self.mock_db_handler.update_task_summary.assert_called_once_with(99, ANY)
        self.assertIn("成功完成", summary)

    @patch('qzen_core.orchestrator.file_handler')
    @patch('qzen_core.orchestrator.shutil')
    @patch('qzen_core.orchestrator.os')
    def test_run_deduplication_core_happy_path(self, mock_os, mock_shutil, mock_file_handler):
        source_path, intermediate_path, allowed_extensions = "/source", "/intermediate", {'.txt'}
        mock_os.path.join.side_effect, mock_os.path.normpath.side_effect, mock_os.path.relpath.side_effect, mock_os.path.splitext.side_effect = os.path.join, os.path.normpath, os.path.relpath, os.path.splitext
        mock_os.path.dirname.return_value, mock_os.path.basename.side_effect = "/intermediate", os.path.basename
        mock_files = [f"{source_path}/unique.txt", f"{source_path}/duplicate.txt", f"{source_path}/another_duplicate.txt"]
        mock_file_handler.scan_files.return_value = mock_files
        def mock_calculate_hash(file_path): return "hash_unique" if "unique" in file_path else ("hash_duplicate" if "duplicate" in file_path else None)
        mock_file_handler.calculate_file_hash.side_effect = mock_calculate_hash
        self.mock_db_handler.create_task_run.return_value = TaskRun(id=1)
        mock_progress_callback, mock_is_cancelled_callback = MagicMock(), MagicMock(return_value=False)
        summary, results = self.orchestrator.run_deduplication_core(source_path, intermediate_path, allowed_extensions, mock_progress_callback, mock_is_cancelled_callback)
        self.assertEqual(mock_shutil.copy2.call_count, 2)
        mock_shutil.copy2.assert_has_calls([call(f"{source_path}/unique.txt", os.path.normpath(os.path.join(intermediate_path, "unique.txt"))), call(f"{source_path}/duplicate.txt", os.path.normpath(os.path.join(intermediate_path, "duplicate.txt")))], any_order=True)
        self.assertEqual(self.mock_db_handler.bulk_insert_documents.call_count, 1)
        self.assertEqual(self.mock_db_handler.bulk_insert_deduplication_results.call_count, 1)
        self.mock_db_handler.update_task_summary.assert_called_once()
        self.assertEqual(mock_progress_callback.call_count, len(mock_files))

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
        # v3.2 修正: 模拟 Document 对象时添加 id
        vec1, vec2 = csr_matrix(np.array([[1, 0, 1]])), csr_matrix(np.array([[0, 1, 1]]))
        doc1 = Document(id=1, file_path="/path/doc1.txt", feature_vector=_vector_to_json(vec1))
        doc2 = Document(id=2, file_path="/path/doc2.txt", feature_vector=_vector_to_json(vec2))
        doc3 = Document(id=3, file_path="/path/doc3.txt", feature_vector=None)
        self.mock_db_handler.get_all_documents.return_value = [doc1, doc2, doc3]
        
        self.orchestrator.prime_similarity_engine()
        
        self.mock_db_handler.get_all_documents.assert_called_once()
        
        # v3.2 修正: 不再检查 Orchestrator 的私有属性，而是检查其对 SimilarityEngine 的公共属性的设置
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
        
        # v3.2 修正: 检查 SimilarityEngine 的公共属性
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
