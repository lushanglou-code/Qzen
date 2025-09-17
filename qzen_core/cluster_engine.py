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
    查找一组字符串的“智能”最长公共前缀。

    此函数不仅查找字符上的最长公共前缀，还包含一个重要的业务逻辑：
    为了生成更具可读性的簇名称，它会避免在单词中间截断。当找到
    第一个不匹配的字符时，它会从不匹配点向前回溯，找到最后一个
    词语分隔符（如空格, _, -），并返回到该分隔符为止的前缀。

    Args:
        strs: 一个包含待比较字符串的列表。

    Returns:
        计算出的最长公共前缀字符串。

    Example:
        >>> find_longest_common_prefix([
        ...     "Qzen 项目 - 需求文档 v1.docx",
        ...     "Qzen 项目 - 技术架构.docx",
        ...     "Qzen 项目 - 会议纪要.docx"
        ... ])
        'Qzen 项目 - ' # 返回到最后一个分隔符，而不是 'Qzen 项目 - '
    """
    if not strs:
        return ""

    # 以最短的字符串作为基准，因为前缀不可能比它更长
    shortest_str = min(strs, key=len)
    
    for i, char in enumerate(shortest_str):
        for other_str in strs:
            if other_str[i] != char:
                # 一旦发现不匹配的字符，立即返回当前位置之前的部分
                prefix = shortest_str[:i]
                
                # 为了避免切分单词，我们从当前位置向前找到最后一个分隔符
                separators = [' ', '_', '-']
                last_separator_pos = -1
                for sep in separators:
                    last_separator_pos = max(last_separator_pos, prefix.rfind(sep))
                
                if last_separator_pos > 0:
                    # 如果找到了分隔符，返回到分隔符之后的位置
                    return prefix[:last_separator_pos + 1]
                
                # 如果没有找到分隔符，则返回原始的公共前缀
                return prefix
    
    # 如果所有字符串完全相同，或者其中一个是另一个的前缀，则最短的字符串就是最长公共前缀
    return shortest_str


class ClusterEngine:
    """
    封装了基于相似度的文档聚类算法。

    此类提供将一组文档根据其内容相似度进行分组的核心功能。
    """

    def cluster_documents(self, feature_matrix: csr_matrix, similarity_threshold: float) -> List[List[int]]:
        """
        使用贪心算法根据相似度阈值对文档进行聚类。

        算法描述:
        1. 计算所有文档对之间的余弦相似度，得到一个相似度矩阵。
        2. 遍历每一个尚未被聚类的文档（索引 `i`）。
        3. 为文档 `i` 创建一个新的簇，并将 `i` 放入该簇。
        4. 再次遍历所有其他尚未被聚类的文档（索引 `j`），如果文档 `j` 与
           文档 `i` 的相似度大于或等于 `similarity_threshold`，则将 `j`
           也加入到当前簇中。
        5. **业务规则**: 只有当一个簇包含多于一个文档时，才被认为是一个
           有效的簇，并被保留下来。

        Args:
            feature_matrix: 一个 CSR 格式的稀疏矩阵，其中每一行代表一个
                            文档的 TF-IDF 特征向量。
            similarity_threshold: 用于判断两个文档是否属于同一簇的相似度
                                阈值 (范围 0.0 到 1.0)。

        Returns:
            一个列表，其中每个子列表包含属于同一个有效簇的文档的索引。
            例如: [[0, 5, 12], [1, 8], [2, 10, 15]]
        """
        num_docs = feature_matrix.shape[0]
        # 预先计算所有文档之间的两两相似度，这是一个 N x N 的矩阵
        sim_matrix = cosine_similarity(feature_matrix)

        # 使用一个布尔列表来跟踪哪些文档已经被分配到簇中
        clustered = [False] * num_docs
        clusters = []

        for i in range(num_docs):
            # 如果当前文档已经被分配过，则跳过
            if clustered[i]:
                continue

            # 为当前文档创建一个新簇，它自己是第一个成员
            current_cluster = [i]
            clustered[i] = True

            # 贪心步骤：遍历其他所有文档，看是否能将它们吸纳进当前簇
            for j in range(i + 1, num_docs):
                if not clustered[j] and sim_matrix[i, j] >= similarity_threshold:
                    current_cluster.append(j)
                    clustered[j] = True
            
            # 业务规则：只有当簇中包含多个文件时，才认为它是一个有意义的簇
            if len(current_cluster) > 1:
                clusters.append(current_cluster)

        return clusters
