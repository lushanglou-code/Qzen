# -*- coding: utf-8 -*-
"""
单元测试模块：测试相似度计算引擎。
"""

import os
import pickle
import unittest

import numpy as np
from scipy.sparse import csr_matrix

# 将项目根目录添加到sys.path，以便导入qzen_core
# 在实际的测试运行器（如pytest）中，这通常是自动处理的
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qzen_core.similarity_engine import SimilarityEngine


class TestSimilarityEngine(unittest.TestCase):
    """测试 SimilarityEngine 类的功能。"""

    def setUp(self):
        """为每个测试用例初始化一个新的 SimilarityEngine 实例和测试数据。"""
        self.engine = SimilarityEngine(max_features=100) # 限制特征数量以保证测试稳定性
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
        # 应该有4个文档
        self.assertEqual(feature_matrix.shape[0], 4)
        # 矩阵中应该包含非零值
        self.assertTrue(feature_matrix.nnz > 0)

    def test_find_top_n_similar(self):
        """测试查找最相似的N个文档的功能。"""
        # 1. 首先向量化文档
        self.engine.vectorize_documents(self.documents)

        # 2. 选择第一个文档作为目标 ("python is a great programming language for beginners")
        target_vector = self.engine.feature_matrix[0]

        # 3. 查找最相似的2个文档
        indices, scores = self.engine.find_top_n_similar(target_vector, n=2)

        # 期望结果：
        # - 最相似的应该是第4个文档 ("python and java are both powerful programming languages")
        # - 第二相似的应该是第2个文档 ("java is another popular programming language")
        self.assertEqual(len(indices), 2)
        self.assertEqual(len(scores), 2)
        self.assertEqual(indices[0], 3) # 索引为3的文档最相似
        self.assertEqual(indices[1], 1) # 索引为1的文档第二相似
        self.assertGreater(scores[0], scores[1]) # 第一个的得分应该更高

    def test_find_similar_raises_error_if_not_vectorized(self):
        """测试在未向量化时调用 find_top_n_similar 是否会引发异常。"""
        # 创建一个虚拟的目标向量
        dummy_vector = csr_matrix(np.random.rand(1, 100))
        with self.assertRaises(ValueError):
            self.engine.find_top_n_similar(dummy_vector, n=1)

    def test_save_and_load_model(self):
        """测试保存和加载 TF-IDF 向量化器模型的功能。"""
        # 1. 训练向量化器
        original_matrix = self.engine.vectorize_documents(self.documents)

        # 2. 保存模型
        model_path = "test_vectorizer.pkl"
        self.engine.save_model(model_path)
        self.assertTrue(os.path.exists(model_path))

        # 3. 创建一个新引擎并加载模型
        new_engine = SimilarityEngine()
        new_engine.load_model(model_path)

        # 4. 验证加载的模型是否与原模型一致
        self.assertEqual(self.engine.vectorizer.vocabulary_, new_engine.vectorizer.vocabulary_)

        # 5. 验证加载的模型是否能产生相同的结果
        new_matrix = new_engine.vectorizer.transform(self.documents)
        np.testing.assert_array_almost_equal(original_matrix.toarray(), new_matrix.toarray())

        # 6. 清理创建的临时文件
        os.remove(model_path)


if __name__ == '__main__':
    # 这使得脚本可以直接运行以执行测试
    unittest.main()