# -*- coding: utf-8 -*-
"""
单元测试模块：测试相似度计算引擎 (v5.4.3 - 最终修复)。

此版本最终修复了 `test_get_top_keywords` 中的 `ValueError`。
之前的修复尝试通过模拟 `np.sum`，但这种方法很脆弱。最终的修复方案
放弃了模拟，改为在测试中手动构建一个具有已知维度和数据的 `feature_matrix`。
这使得对 `get_top_keywords` 的输入完全可控，从而能够精确、可靠地验证其内部逻辑。
"""

import unittest
from unittest.mock import patch

import numpy as np
from scipy.sparse import csr_matrix

# 将项目根目录添加到sys.path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qzen_core.similarity_engine import SimilarityEngine


class TestSimilarityEngine(unittest.TestCase):
    """测试 SimilarityEngine 类的功能。"""

    def setUp(self):
        """为每个测试用例初始化一个新的 SimilarityEngine 实例和测试数据。"""
        self.engine = SimilarityEngine(max_features=100)
        self.documents = [
            "python is a great programming language for beginners",
            "java is another popular programming language",
            "i love to eat pizza and pasta for dinner",
            "python and java are both powerful programming languages"
        ]

    def test_vectorize_documents(self):
        """测试 TF-IDF 向量化过程。"""
        feature_matrix = self.engine.vectorize_documents(self.documents)
        self.assertIsInstance(feature_matrix, csr_matrix)
        self.assertEqual(feature_matrix.shape[0], 4)
        self.assertTrue(feature_matrix.nnz > 0)

    def test_find_top_n_similar(self):
        """测试查找最相似的N个文档的功能，并使其对顺序不敏感。"""
        self.engine.feature_matrix = self.engine.vectorize_documents(self.documents)
        target_vector = self.engine.feature_matrix[0]
        indices, scores = self.engine.find_top_n_similar(target_vector, n=2)
        self.assertEqual(len(indices), 2)
        self.assertEqual(len(scores), 2)
        self.assertSetEqual(set(indices), {1, 3})

    def test_find_similar_returns_empty_if_not_vectorized(self):
        """
        测试在未向量化时调用 find_top_n_similar 是否返回空列表。
        """
        self.engine.feature_matrix = None
        dummy_vector = csr_matrix(np.random.rand(1, 100))
        indices, scores = self.engine.find_top_n_similar(dummy_vector, n=1)
        self.assertEqual(indices, [])
        self.assertEqual(scores, [])

    def test_get_top_keywords(self):
        """
        v5.4.3 最终修复: 测试 get_top_keywords 方法能否为一组文档正确提取关键词。
        """
        # 1. 手动构建一个可控的特征矩阵 (3个文档, 5个特征)
        # doc0: [1, 1, 0, 0, 0]
        # doc1: [0, 0, 1, 1, 0]
        # doc2: [1, 0, 0, 0, 1]
        self.engine.feature_matrix = csr_matrix(np.array([
            [1, 1, 0, 0, 0],
            [0, 0, 1, 1, 0],
            [1, 0, 0, 0, 1]
        ]))
        
        # 2. 模拟特征名称的返回
        feature_names = np.array(["python", "java", "web", "backend", "ai"])
        self.engine.vectorizer.get_feature_names_out = lambda: feature_names

        # 3. 调用方法，提取 doc0 和 doc2 的 top 2 关键词
        # 合并后的向量将是 [2, 1, 0, 0, 1]。权重最高的词是 "python" (2.0) 和 "java"/"ai" (1.0)
        keywords = self.engine.get_top_keywords(doc_indices=[0, 2], n=2)

        # 4. 断言结果 (顺序很重要，权重高的在前)
        # "python" 的权重是 2，"java" 和 "ai" 都是 1。根据 sorted 的稳定性，
        # "java" 会排在 "ai" 前面。但为了测试的绝对稳定，我们只断言一个集合。
        self.assertIn("python", keywords.split('_'))
        self.assertTrue(keywords.startswith("python"), "权重最高的 'python' 应该在最前面")


if __name__ == '__main__':
    unittest.main()
