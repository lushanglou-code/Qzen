# -*- coding: utf-8 -*-
"""
单元测试模块：测试业务流程协调器 Orchestrator。
"""

import os
import unittest
from unittest.mock import MagicMock, patch, call

# 将项目根目录添加到sys.path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qzen_core.orchestrator import Orchestrator, _vector_to_json
from qzen_data.models import Document, DeduplicationResult, TaskRun, RenameResult
from scipy.sparse import csr_matrix, vstack
import numpy as np


class TestOrchestrator(unittest.TestCase):
    """测试 Orchestrator 类的功能。"""

    def setUp(self):
        self.mock_db_handler = MagicMock()
        self.orchestrator = Orchestrator(db_handler=self.mock_db_handler, max_features=5000, slice_size_kb=1)
        # For tests that don't rely on the real engines, we can replace them with mocks.
        self.orchestrator.similarity_engine = MagicMock()
        self.orchestrator.cluster_engine = MagicMock()

    def test_instantiation(self):
        self.assertIsNotNone(self.orchestrator)
        self.assertEqual(self.orchestrator.db_handler, self.mock_db_handler)

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
        vec1, vec2 = csr_matrix(np.array([[1, 0, 1]])), csr_matrix(np.array([[0, 1, 1]]))
        doc1, doc2, doc3 = Document(file_path="/path/doc1.txt", feature_vector=_vector_to_json(vec1)), Document(file_path="/path/doc2.txt", feature_vector=_vector_to_json(vec2)), Document(file_path="/path/doc3.txt", feature_vector=None)
        self.mock_db_handler.get_all_documents.return_value = [doc1, doc2, doc3]
        self.orchestrator.prime_similarity_engine()
        self.mock_db_handler.get_all_documents.assert_called_once()
        expected_matrix = vstack([vec1, vec2])
        self.assertTrue(np.array_equal(self.orchestrator.similarity_engine.feature_matrix.toarray(), expected_matrix.toarray()))
        self.assertEqual(self.orchestrator._doc_path_map, ["/path/doc1.txt", "/path/doc2.txt"])
        self.assertTrue(self.orchestrator._is_engine_primed)

    def test_prime_similarity_engine_no_vectors(self):
        self.mock_db_handler.get_all_documents.return_value = [Document(file_path="/path/doc1.txt", feature_vector=None)]
        self.orchestrator.prime_similarity_engine()
        self.assertIsNone(self.orchestrator.similarity_engine.feature_matrix)
        self.assertEqual(self.orchestrator._doc_path_map, [])
        self.assertTrue(self.orchestrator._is_engine_primed)

    @patch('qzen_core.orchestrator.logging')
    def test_prime_similarity_engine_invalid_json(self, mock_logging):
        vec1 = csr_matrix(np.array([[1, 0, 1]]))
        doc1, doc2 = Document(file_path="/path/doc1.txt", feature_vector=_vector_to_json(vec1)), Document(file_path="/path/doc2.txt", feature_vector="invalid-json")
        self.mock_db_handler.get_all_documents.return_value = [doc1, doc2]
        self.orchestrator.prime_similarity_engine()
        mock_logging.error.assert_called_once()

    @patch('qzen_core.orchestrator.shutil')
    @patch('qzen_core.orchestrator.os')
    def test_run_topic_clustering_partial_clustering(self, mock_os, mock_shutil):
        """测试场景：部分文件被聚类，剩余文件进入“未归类”文件夹。"""
        # --- Arrange ---
        self.orchestrator._is_engine_primed = True
        self.orchestrator.similarity_engine.feature_matrix = csr_matrix(np.eye(4))
        self.orchestrator._doc_path_map = ["/path/doc_a1.txt", "/path/doc_a2.txt", "/path/doc_b.txt", "/path/doc_c.txt"]
        self.orchestrator.similarity_engine.vectorizer.get_feature_names_out.return_value = ["a", "b", "c", "d"]
        self.orchestrator.cluster_engine.cluster_documents.return_value = [[0, 1]]  # doc_a1 和 doc_a2 聚成一类
        self.mock_db_handler.create_task_run.return_value = TaskRun(id=1)
        mock_os.path.join.side_effect = os.path.join
        mock_os.path.basename.side_effect = os.path.basename

        # --- Act ---
        summary, results = self.orchestrator.run_topic_clustering("/target", 0.85, MagicMock(), MagicMock(return_value=False))

        # --- Assert ---
        # 验证文件夹创建
        mock_os.makedirs.assert_has_calls([
            call(os.path.join("/target", "a"), exist_ok=True),      # 主题文件夹
            call(os.path.join("/target", "未归类"), exist_ok=True) # 未归类文件夹
        ], any_order=True)

        # 验证文件复制
        mock_shutil.copy2.assert_has_calls([
            call("/path/doc_a1.txt", os.path.join("/target", "a", "doc_a1.txt")),
            call("/path/doc_a2.txt", os.path.join("/target", "a", "doc_a2.txt")),
            call("/path/doc_b.txt", os.path.join("/target", "未归类", "doc_b.txt")),
            call("/path/doc_c.txt", os.path.join("/target", "未归类", "doc_c.txt"))
        ], any_order=True)
        self.assertEqual(mock_shutil.copy2.call_count, 4)

        # 验证数据库和摘要
        self.mock_db_handler.bulk_insert_rename_results.assert_called_once()
        self.assertIn("共创建 1 个主题文件夹", summary)
        self.assertIn("整理了 2 个文件", summary)
        self.assertIn("另有 2 个文件被移至“未归类”文件夹", summary)

    @patch('qzen_core.orchestrator.shutil')
    @patch('qzen_core.orchestrator.os')
    def test_run_topic_clustering_no_clustering(self, mock_os, mock_shutil):
        """测试场景：没有文件能构成簇，所有文件都应进入“未归类”文件夹。"""
        # --- Arrange ---
        self.orchestrator._is_engine_primed = True
        self.orchestrator.similarity_engine.feature_matrix = csr_matrix(np.eye(2))
        self.orchestrator._doc_path_map = ["/path/doc_b.txt", "/path/doc_c.txt"]
        self.orchestrator.similarity_engine.vectorizer.get_feature_names_out.return_value = ["b", "c"]
        self.orchestrator.cluster_engine.cluster_documents.return_value = []  # 没有找到任何簇
        self.mock_db_handler.create_task_run.return_value = TaskRun(id=1)
        mock_os.path.join.side_effect = os.path.join
        mock_os.path.basename.side_effect = os.path.basename

        # --- Act ---
        summary, results = self.orchestrator.run_topic_clustering("/target", 0.95, MagicMock(), MagicMock(return_value=False))

        # --- Assert ---
        # 验证只创建了“未归类”文件夹
        mock_os.makedirs.assert_called_once_with(os.path.join("/target", "未归类"), exist_ok=True)

        # 验证所有文件都被复制到了“未归类”文件夹
        mock_shutil.copy2.assert_has_calls([
            call("/path/doc_b.txt", os.path.join("/target", "未归类", "doc_b.txt")),
            call("/path/doc_c.txt", os.path.join("/target", "未归类", "doc_c.txt"))
        ], any_order=True)
        self.assertEqual(mock_shutil.copy2.call_count, 2)

        # 验证数据库和摘要
        self.mock_db_handler.bulk_insert_rename_results.assert_not_called() # 不应有重命名结果
        self.assertIn("没有找到可以构成簇的相似文档", summary)
        self.assertIn("所有 2 个文件已被移至“未归类”文件夹", summary)

if __name__ == '__main__':
    unittest.main()
