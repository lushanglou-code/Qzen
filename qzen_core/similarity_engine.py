# -*- coding: utf-8 -*-
"""
相似度计算引擎模块。

封装了文档的特征提取（TF-IDF）、相似度计算（余弦相似度）以及
高效的近邻搜索算法。
"""

import pickle
from typing import List, Tuple

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SimilarityEngine:
    """
    封装了文档相似度计算和搜索的核心功能。

    该引擎的核心是 scikit-learn 的 `TfidfVectorizer`，它能将原始
    文本文档集合转换为一个 TF-IDF 特征矩阵，为后续的量化比较奠定基础。

    Attributes:
        vectorizer (TfidfVectorizer): scikit-learn 的 TF-IDF 向量化器实例。
        feature_matrix (csr_matrix | None): 由 `vectorize_documents` 方法生成的
                                          文档-词项稀疏矩阵。在向量化之前为 None。
    """

    def __init__(self, max_features: int = 5000):
        """
        初始化相似度引擎。

        Args:
            max_features (int): TF-IDF 向量化器构建词汇表时使用的最大特征
                              （词汇）数量。这是控制内存使用和计算复杂度的
                              关键参数。
        """
        # 初始化TF-IDF向量化器，并设置常用参数以优化性能和结果。
        # - max_df=0.95: 忽略在超过 95% 的文档中都出现的词语（通常是无意义的常用词）。
        # - min_df=2: 忽略在少于 2 个文档中出现的词语（过于稀有，可能对相似度贡献不大）。
        # - stop_words='english': 使用内置的英文停用词列表。
        self.vectorizer = TfidfVectorizer(
            max_features=max_features, 
            max_df=0.95, 
            min_df=2, 
            stop_words='english'
        )
        self.feature_matrix: csr_matrix | None = None

    def vectorize_documents(self, documents: List[str]) -> csr_matrix:
        """
        使用TF-IDF算法将一组文档内容转化为特征向量矩阵。

        此方法会“训练”向量化器，即根据输入的所有文档内容构建一个词汇表，
        然后将每个文档转换为一个数值型特征向量。

        Args:
            documents: 一个包含原始文档内容的字符串列表。

        Returns:
            一个 CSR 格式的稀疏矩阵，其中每行代表一个文档的TF-IDF特征向量。
        """
        # 使用 fit_transform 来学习词汇表并同时转换文本数据为特征矩阵
        self.feature_matrix = self.vectorizer.fit_transform(documents)
        return self.feature_matrix

    def find_top_n_similar(self, target_vector: csr_matrix, n: int = 10) -> Tuple[List[int], List[float]]:
        """
        在已有的特征矩阵中，查找与目标向量最相似的前 N 个向量。

        此方法采用了一种高效的查找策略：
        1. 计算目标向量与矩阵中所有向量的余弦相似度。
        2. 使用 `numpy.argpartition` 进行部分排序，这是一个 O(N) 的操作，
           远快于完全排序 O(N log N)。它能快速找到相似度最高的 `n+1`
           个候选项，而无需对整个列表进行排序。
        3. 从候选项中排除与目标自身最相似的结果。
        4. 对最终的 top N 结果进行排序，以确保返回的列表是按相似度降序排列的。

        Args:
            target_vector: 目标文档的特征向量，形状应为 (1, num_features)。
            n: 希望返回的最相似文档的数量。

        Returns:
            一个元组，包含两个列表：
            - 第一个列表是相似文档在原始特征矩阵中的索引。
            - 第二个列表是与索引对应的余弦相似度得分。
        
        Raises:
            ValueError: 如果特征矩阵尚未被计算（即 `feature_matrix` 为 None）。
        """
        if self.feature_matrix is None:
            raise ValueError("特征矩阵尚未被计算，请先调用 vectorize_documents。")

        # 步骤 1: 计算目标向量与所有其他向量的余弦相似度
        sim_scores = cosine_similarity(target_vector, self.feature_matrix)
        sim_scores = sim_scores.flatten() # 将结果从 [[...]] 展平为 [...] 

        # 步骤 2: 使用 argpartition 高效找到 top N+1 的候选项
        # 我们取 n+1 是因为结果中很可能包含查询向量自身（相似度为1.0）
        num_docs = self.feature_matrix.shape[0]
        k = min(n + 1, num_docs)
        top_indices = np.argpartition(sim_scores, -k)[-k:]

        # 步骤 3: 过滤掉与自身比较的结果
        # 比较浮点数时，使用一个小的容差而不是直接与 1.0 比较
        top_indices = [i for i in top_indices if sim_scores[i] < 0.99999]

        # 步骤 4: 对最终的候选项按相似度得分进行降序排序
        sorted_indices = sorted(top_indices, key=lambda i: sim_scores[i], reverse=True)
        
        # 截取最终的 top N 个结果
        final_indices = sorted_indices[:n]
        final_scores = [sim_scores[i] for i in final_indices]

        return final_indices, final_scores

    def save_model(self, file_path: str) -> None:
        """
        将训练好的TF-IDF向量化器序列化到磁盘。

        注意：此功能目前未在主应用流程中使用。当前应用在每次运行时
        都会重新训练向量化器。提供此方法是为了未来可能的扩展，例如
        实现模型的持久化以加快启动速度。

        Args:
            file_path: 模型要保存到的文件路径。
        """
        with open(file_path, 'wb') as f:
            pickle.dump(self.vectorizer, f)

    def load_model(self, file_path: str) -> None:
        """
        从磁盘加载之前保存的TF-IDF向量化器。

        注意：此功能目前未在主应用流程中使用。

        Args:
            file_path: 模型的路径。
        """
        with open(file_path, 'rb') as f:
            self.vectorizer = pickle.load(f)
