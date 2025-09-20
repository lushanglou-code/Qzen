# -*- coding: utf-8 -*-
"""
单元测试模块：测试文件聚类引擎 (v2.2 - TDD 修正版)。

此版本新增了一个预期会失败的测试，用于复现因“脏数据”导致的崩溃，
以便驱动后续的修复。
"""

import os
import json
import shutil
import unittest
from collections import defaultdict
from unittest.mock import MagicMock, patch, call, ANY

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer

# 将项目根目录添加到sys.path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qzen_core.cluster_engine import ClusterEngine
from qzen_data.models import Document


def _vector_to_json(vector: csr_matrix) -> str:
    """将稀疏矩阵 (CSR Matrix) 序列化为 JSON 字符串。"""
    return json.dumps({
        'data': vector.data.tolist(),
        'indices': vector.indices.tolist(),
        'indptr': vector.indptr.tolist(),
        'shape': vector.shape
    })

def _create_mock_vectors():
    """创建一个可预测的模拟特征向量集。"""
    corpus = [
        "软件架构 设计模式 微服务", # Doc 0 (Tech)
        "软件架构 微服务 敏捷开发", # Doc 1 (Tech)
        "市场营销 商业智能 用户增长", # Doc 2 (Biz)
        "商业智能 用户增长 市场策略"  # Doc 3 (Biz)
    ]
    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform(corpus)
    return [_vector_to_json(vectors.getrow(i)) for i in range(len(corpus))], vectorizer, corpus


class TestClusterEngine(unittest.TestCase):
    """测试 ClusterEngine 类的功能。"""

    def setUp(self):
        """为每个测试用例设置临时目录和模拟对象。"""
        self.test_dir = "temp_cluster_test_dir"
        self.target_dir = os.path.normpath(os.path.join(self.test_dir, "target"))
        os.makedirs(self.target_dir, exist_ok=True)

        self.mock_db_handler = MagicMock()
        self.mock_sim_engine = MagicMock()
        self.engine = ClusterEngine(self.mock_db_handler, self.mock_sim_engine)

        self.mock_vectors, self.mock_vectorizer, self.mock_contents = _create_mock_vectors()
        self.mock_docs = []
        for i in range(4):
            file_path = os.path.join(self.target_dir, f"doc_{i}.txt")
            with open(file_path, 'w') as f: f.write("content")
            doc = Document(
                file_hash=f"hash{i}",
                file_path=file_path,
                content_slice=self.mock_contents[i],
                feature_vector=self.mock_vectors[i]
            )
            doc.id = i
            self.mock_docs.append(doc)

    def tearDown(self):
        """在每个测试用例后清理临时目录。"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('qzen_core.cluster_engine.KMeans')
    def test_run_clustering_full_workflow(self, MockKMeans):
        """测试 run_clustering 方法是否能正确执行完整的 K-Means + 相似度聚类工作流。"""
        mock_kmeans_instance = MockKMeans.return_value
        mock_kmeans_instance.labels_ = np.array([0, 0, 1, 1])
        self.mock_sim_engine.vectorizer = self.mock_vectorizer

        tech_docs = self.mock_docs[0:2]
        biz_docs = self.mock_docs[2:4]
        def get_docs_side_effect(path):
            norm_path = os.path.normpath(path)
            if norm_path == self.target_dir:
                return self.mock_docs
            elif os.path.basename(norm_path) == '0':
                return tech_docs
            elif os.path.basename(norm_path) == '1':
                return biz_docs
            return []

        with patch.object(self.engine, '_get_documents_from_db', side_effect=get_docs_side_effect) as mock_get_docs:
            self.engine.run_clustering(self.target_dir, k=2, similarity_threshold=0.5)
            expected_db_calls = [
                call(self.target_dir),
                call(os.path.join(self.target_dir, '0')),
                call(os.path.join(self.target_dir, '1'))
            ]
            mock_get_docs.assert_has_calls(expected_db_calls, any_order=True)
            self.assertEqual(mock_get_docs.call_count, 3)
            self.assertEqual(self.mock_db_handler.bulk_update_documents.call_count, 3)
            final_paths = {os.path.join(r, f) for r, d, f_list in os.walk(self.target_dir) for f in f_list}
            self.assertEqual(len(final_paths), 4, "最终应仍有4个文件")
            self.assertTrue(any("软件架构_微服务" in p for p in final_paths), "应创建了包含技术主题词的文件夹")
            self.assertTrue(any("用户增长_商业智能" in p for p in final_paths), "应创建了包含业务主题词的文件夹")
            self.assertFalse(os.path.exists(os.path.join(self.target_dir, "doc_0.txt")), "原始文件应被移动")

    def test_run_clustering_with_insufficient_docs(self):
        """测试当文档数量少于 K 值时，聚类是否能优雅地中止。"""
        with patch.object(self.engine, '_get_documents_from_db', return_value=self.mock_docs[:1]):
            with self.assertLogs(level='WARNING') as cm:
                self.engine.run_clustering(self.target_dir, k=2, similarity_threshold=0.5)
                self.assertTrue(any("小于 K值" in log for log in cm.output))
            self.mock_db_handler.bulk_update_documents.assert_not_called()

    def test_run_clustering_is_robust_against_empty_vectors(self):
        """
        验证缺陷：当数据库中存在 feature_vector 为空字符串的“脏数据”时，
        聚类引擎不应崩溃，而应能优雅地跳过这些记录。
        """
        # 1. Arrange: 创建一个包含“脏数据”的文档列表
        valid_doc_1 = self.mock_docs[0]
        valid_doc_2 = self.mock_docs[1]
        poison_doc = Document(
            file_hash="poison_hash",
            file_path=os.path.join(self.target_dir, "poison.txt"),
            content_slice="some content",
            feature_vector=""  # 关键：“脏数据”
        )
        poison_doc.id = 99
        with open(poison_doc.file_path, 'w') as f: f.write("content")

        # 确保有足够的文件来触发K-Means
        docs_from_db = [valid_doc_1, valid_doc_2, poison_doc]

        # 模拟 _get_documents_from_db 返回这个混合列表
        with patch.object(self.engine, '_get_documents_from_db', return_value=docs_from_db):
            # 2. Act & Assert: 执行聚类，并断言它不会因脏数据而崩溃
            try:
                # K=2，现在有足够的文件来触发 K-Means
                self.engine.run_clustering(self.target_dir, k=2, similarity_threshold=0.8)
                # 如果代码能执行到这里而没有抛出 JSONDecodeError，就证明了健壮性
                assert True
            except Exception as e:
                # 如果有任何异常，测试就失败
                self.fail(f"Clustering engine crashed with an unexpected exception: {e}")

if __name__ == '__main__':
    unittest.main()
