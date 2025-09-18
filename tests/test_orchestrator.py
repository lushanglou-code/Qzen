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
        self.mock_similarity_engine = MagicMock()
        self.mock_cluster_engine = MagicMock()
        self.orchestrator = Orchestrator(db_handler=self.mock_db_handler, max_features=5000, slice_size_kb=1)
        self.orchestrator.similarity_engine = self.mock_similarity_engine
        self.orchestrator.cluster_engine = self.mock_cluster_engine

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

    @patch('qzen_core.orchestrator.file_handler')
    def test_run_vectorization_happy_path(self, mock_file_handler):
        doc1, doc2 = Document(file_path="/path/doc1.txt"), Document(file_path="/path/doc2.txt")
        doc1.id, doc2.id = 1, 2
        self.mock_db_handler.get_documents_without_vectors.return_value = [doc1, doc2]
        mock_file_handler.get_content_slice.side_effect = ["content1", "content2"]
        mock_feature_matrix = csr_matrix(np.array([[1, 2, 0], [0, 3, 4]]))
        self.mock_similarity_engine.vectorize_documents.return_value = mock_feature_matrix
        result_summary = self.orchestrator.run_vectorization(MagicMock(), MagicMock(return_value=False))
        self.mock_db_handler.get_documents_without_vectors.assert_called_once()
        self.mock_similarity_engine.vectorize_documents.assert_called_once_with(["content1", "content2"])
        self.mock_db_handler.bulk_update_documents.assert_called_once()
        updated_docs = self.mock_db_handler.bulk_update_documents.call_args[0][0]
        self.assertEqual(updated_docs[0].feature_vector, _vector_to_json(mock_feature_matrix[0]))

    def test_run_vectorization_no_docs_to_process(self):
        self.mock_db_handler.get_documents_without_vectors.return_value = []
        result_summary = self.orchestrator.run_vectorization(MagicMock(), MagicMock(return_value=False))
        self.mock_db_handler.get_documents_without_vectors.assert_called_once()
        self.mock_similarity_engine.vectorize_documents.assert_not_called()
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
        self.assertTrue(np.array_equal(self.orchestrator.similarity_engine.feature_matrix.toarray(), vec1.toarray()))
        self.assertEqual(self.orchestrator._doc_path_map, ["/path/doc1.txt"])
        mock_logging.error.assert_called_once()

    @patch('qzen_core.orchestrator.find_longest_common_prefix')
    @patch('qzen_core.orchestrator.shutil')
    @patch('qzen_core.orchestrator.os')
    def test_run_clustering_and_renaming_happy_path(self, mock_os, mock_shutil, mock_find_prefix):
        self.orchestrator._is_engine_primed = True
        self.orchestrator.similarity_engine.feature_matrix = csr_matrix(np.array([[1,1],[1,1],[0,0]]))
        self.orchestrator._doc_path_map = ["/path/report_v1.txt", "/path/report_v2.txt", "/path/other.txt"]
        self.mock_cluster_engine.cluster_documents.return_value = [[0, 1]]
        mock_find_prefix.return_value = "report"
        mock_os.path.join.side_effect = os.path.join
        mock_os.path.splitext.side_effect = os.path.splitext
        mock_os.path.basename.side_effect = os.path.basename
        self.mock_db_handler.create_task_run.return_value = TaskRun(id=1)
        
        target_dir = "/target"
        cluster_dir_name = "report"
        expected_cluster_dir = os.path.join(target_dir, cluster_dir_name)

        summary, results = self.orchestrator.run_clustering_and_renaming(target_dir, 0.85, MagicMock(), MagicMock(return_value=False))
        
        self.mock_cluster_engine.cluster_documents.assert_called_once()
        mock_os.makedirs.assert_called_with(expected_cluster_dir, exist_ok=True)
        
        expected_calls = [
            call("/path/report_v1.txt", os.path.join(expected_cluster_dir, "report_1.txt")),
            call("/path/report_v2.txt", os.path.join(expected_cluster_dir, "report_2.txt"))
        ]
        mock_shutil.copy2.assert_has_calls(expected_calls, any_order=True)
        self.mock_db_handler.bulk_insert_rename_results.assert_called_once()
        saved_results = self.mock_db_handler.bulk_insert_rename_results.call_args[0][0]
        self.assertEqual(len(saved_results), 2)
        self.assertIsInstance(saved_results[0], RenameResult)
        self.assertIn("聚类完成！", summary)

    def test_run_clustering_and_renaming_no_clusters_found(self):
        self.orchestrator._is_engine_primed = True
        self.orchestrator.similarity_engine.feature_matrix = csr_matrix(np.array([[1,1],[0,0]]))
        self.mock_cluster_engine.cluster_documents.return_value = []
        self.mock_db_handler.create_task_run.return_value = TaskRun(id=1)
        summary, results = self.orchestrator.run_clustering_and_renaming("/target", 0.85, MagicMock(), MagicMock(return_value=False))
        self.mock_cluster_engine.cluster_documents.assert_called_once()
        self.assertIn("没有找到可以构成簇", summary)
        self.assertEqual(len(results), 0)
        self.mock_db_handler.bulk_insert_rename_results.assert_not_called()

if __name__ == '__main__':
    unittest.main()
