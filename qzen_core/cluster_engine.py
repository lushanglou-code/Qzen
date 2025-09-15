# -*- coding: utf-8 -*-
"""
文件聚类引擎模块。

封装了将相似文档分组（聚类）的算法，以及为文件簇生成新名称的逻辑。
"""

import os
from typing import List

from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity


def find_longest_common_prefix(strs: List[str]) -> str:
    """
    查找一组字符串的最长公共前缀。

    Args:
        strs: 字符串列表。

    Returns:
        最长的公共前缀字符串。
    """
    if not strs:
        return ""

    # 以最短的字符串作为基准，因为前缀不可能比它更长
    shortest_str = min(strs, key=len)
    
    for i, char in enumerate(shortest_str):
        for other_str in strs:
            if other_str[i] != char:
                # 一旦发现不匹配的字符，立即返回当前位置之前的部分
                # 同时，为了避免切分单词，我们从当前位置向前找到最后一个分隔符
                prefix = shortest_str[:i]
                # 常见的单词分隔符
                separators = [' ', '_', '-']
                last_separator_pos = -1
                for sep in separators:
                    last_separator_pos = max(last_separator_pos, prefix.rfind(sep))
                
                if last_separator_pos > 0:
                    return prefix[:last_separator_pos + 1]
                return prefix
    
    return shortest_str


class ClusterEngine:
    """
    封装了基于相似度的文档聚类算法。
    """

    def cluster_documents(self, feature_matrix: csr_matrix, similarity_threshold: float) -> List[List[int]]:
        """
        使用贪心算法根据相似度阈值对文档进行聚类。

        Args:
            feature_matrix: 文档的TF-IDF特征矩阵。
            similarity_threshold: 用于判断两个文档是否属于同一簇的相似度阈值 (0.0 到 1.0)。

        Returns:
            一个列表，其中每个子列表包含属于同一个簇的文档的索引。
            例如: [[0, 5, 12], [1, 8], [2, 10, 15]]
        """
        num_docs = feature_matrix.shape[0]
        # 计算所有文档之间的两两相似度
        sim_matrix = cosine_similarity(feature_matrix)

        # 记录哪些文档已经被分配到簇中
        clustered = [False] * num_docs
        clusters = []

        for i in range(num_docs):
            if clustered[i]:
                continue

            # 为当前文档创建一个新簇
            current_cluster = [i]
            clustered[i] = True

            # 遍历其他所有文档，看是否能加入当前簇
            for j in range(i + 1, num_docs):
                if not clustered[j] and sim_matrix[i, j] >= similarity_threshold:
                    current_cluster.append(j)
                    clustered[j] = True
            
            # 只有当簇中包含多个文件时，才认为它是一个有效的簇
            if len(current_cluster) > 1:
                clusters.append(current_cluster)

        return clusters
