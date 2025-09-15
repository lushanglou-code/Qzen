# -*- coding: utf-8 -*-
"""
相似度计算引擎模块。

封装了文档的特征提取（TF-IDF）、相似度计算（余弦相似度）以及近邻搜索。
"""

import pickle
from typing import List

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SimilarityEngine:
    """
    封装了文档相似度计算和搜索的核心功能。
    """

    def __init__(self, max_features: int = 5000):
        """
        初始化相似度引擎。

        Args:
            max_features (int): TF-IDF向量化器使用的最大特征（词汇）数量。
        """
        # 初始化TF-IDF向量化器，并设置常用参数以优化性能和结果
        # max_df=0.95: 忽略在超过95%的文档中出现的词语（通常是停用词）
        # min_df=2: 忽略在少于2个文档中出现的词语（稀有词）
        self.vectorizer = TfidfVectorizer(max_features=max_features, max_df=0.95, min_df=2, stop_words='english')
        self.feature_matrix: csr_matrix | None = None

    def vectorize_documents(self, documents: List[str]) -> csr_matrix:
        """
        使用TF-IDF算法将一组文档内容转化为特征向量矩阵。

        该方法会训练向量化器（如果尚未训练），并返回所有文档的向量表示。

        Args:
            documents (List[str]): 文档内容的字符串列表。

        Returns:
            csr_matrix: 一个稀疏矩阵，每行代表一个文档的TF-IDF特征向量。
        """
        # 使用fit_transform来学习词汇表并转换文本数据
        self.feature_matrix = self.vectorizer.fit_transform(documents)
        return self.feature_matrix

    def find_top_n_similar(self, target_vector: csr_matrix, n: int = 10) -> tuple[list[int], list[float]]:
        """
        在已有的特征矩阵中，查找与目标向量最相似的前N个向量。

        Args:
            target_vector (csr_matrix): 目标文档的特征向量。
            n (int): 希望返回的最相似文档的数量。

        Returns:
            tuple[list[int], list[float]]: 一个元组，包含两个列表：
                                           - 相似文档的索引列表。
                                           - 对应的余弦相似度得分列表。
        
        Raises:
            ValueError: 如果特征矩阵尚未被计算。
        """
        if self.feature_matrix is None:
            raise ValueError("特征矩阵尚未被计算，请先调用 vectorize_documents。")

        # 计算目标向量与所有其他向量的余弦相似度
        sim_scores = cosine_similarity(target_vector, self.feature_matrix)

        # 将相似度得分矩阵展平为一维数组
        sim_scores = sim_scores.flatten()

        # 获取排序后的索引，并排除掉自身（相似度最高的通常是自己）
        # 使用 argpartition 来进行部分排序，比 argsort 更高效
        top_indices = np.argpartition(sim_scores, -n - 1)[-n - 1:]
        # 过滤掉与自身比较的索引
        top_indices = [i for i in top_indices if sim_scores[i] < 0.9999] # 避免浮点数精度问题

        # 按相似度降序排序
        sorted_indices = sorted(top_indices, key=lambda i: sim_scores[i], reverse=True)
        
        # 提取最终的索引和分数
        final_indices = sorted_indices[:n]
        final_scores = [sim_scores[i] for i in final_indices]

        return final_indices, final_scores

    def save_model(self, file_path: str) -> None:
        """
        将训练好的TF-IDF向量化器序列化到磁盘。

        Args:
            file_path (str): 模型要保存到的路径。
        """
        with open(file_path, 'wb') as f:
            pickle.dump(self.vectorizer, f)

    def load_model(self, file_path: str) -> None:
        """
        从磁盘加载之前保存的TF-IDF向量化器。

        Args:
            file_path (str): 模型的路径。
        """
        with open(file_path, 'rb') as f:
            self.vectorizer = pickle.load(f)
