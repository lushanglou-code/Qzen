# -*- coding: utf-8 -*-
"""
相似度计算引擎模块。

封装了文档的特征提取（TF-IDF）、相似度计算（余弦相似度）以及
高效的近邻搜索算法。该引擎经过特别配置，以支持高效的中文文本处理。
"""

import logging
import pickle
from typing import List, Tuple

import jieba  # 引入 jieba 分词库
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SimilarityEngine:
    """
    封装了文档相似度计算和搜索的核心功能。

    该引擎的核心是 scikit-learn 的 `TfidfVectorizer`。通过为其提供一个
    集成了 `jieba` 分词的自定义 `tokenizer`，该引擎能够将原始的中文
    文本文档集合，高效地转换为一个可用于量化比较的 TF-IDF 特征矩阵。

    Attributes:
        vectorizer (TfidfVectorizer): 一个为处理中文而特别配置的 scikit-learn
                                  TF-IDF 向量化器实例。
        feature_matrix (csr_matrix | None): 由 `vectorize_documents` 方法生成的
                                          文档-词项稀疏矩阵。在向量化之前为 None。
        stopwords (set[str]): 从外部文件和用户配置中加载的、统一的停用词集合。
    """

    def __init__(self, max_features: int = 5000, stopwords_path: str = "stopwords.txt", custom_stopwords: List[str] = None):
        """
        初始化相似度引擎，并配置中文处理流程。

        Args:
            max_features (int): TF-IDF 向量化器构建词汇表时使用的最大特征
                              （词汇）数量。这是控制内存使用和计算复杂度的
                              关键参数。
            stopwords_path (str): 内置停用词文件的路径。
            custom_stopwords (List[str] | None): 一个包含用户自定义停用词的列表。
        """
        self.stopwords = set()
        self.stopwords_path = stopwords_path  # 保存路径以备后续热更新
        self.update_stopwords(custom_stopwords) # 调用新的更新方法完成初始加载

        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            max_df=0.95,
            min_df=2,
            tokenizer=self._chinese_tokenizer,
            token_pattern=None
        )
        self.feature_matrix: csr_matrix | None = None

    def update_stopwords(self, custom_stopwords: List[str] = None) -> None:
        """
        清空并重新加载所有停用词（内置+自定义），实现停用词库的动态更新。

        Args:
            custom_stopwords: 一个包含新的用户自定义停用词的列表。
        """
        self.stopwords.clear()
        try:
            with open(self.stopwords_path, 'r', encoding='utf-8') as f:
                for line in f:
                    self.stopwords.add(line.strip().lower())
            logging.info(f"成功从 {self.stopwords_path} 加载 {len(self.stopwords)} 个内置停用词。")
        except FileNotFoundError:
            logging.warning(f"内置停用词文件 {self.stopwords_path} 未找到。")

        if custom_stopwords:
            before_count = len(self.stopwords)
            for word in custom_stopwords:
                if word.strip():
                    self.stopwords.add(word.strip().lower())
            added_count = len(self.stopwords) - before_count
            logging.info(f"成功加载并合并 {added_count} 个自定义停用词。")
        
        logging.info(f"停用词库准备就绪，共包含 {len(self.stopwords)} 个唯一停用词。")

    def _chinese_tokenizer(self, text: str) -> List[str]:
        """
        自定义的中文分词器，供 TfidfVectorizer 调用。
        """
        words = jieba.cut(text)
        return [word for word in words if word.lower() not in self.stopwords and len(word) > 1]

    def vectorize_documents(self, documents: List[str]) -> csr_matrix:
        """
        使用TF-IDF算法将一组文档内容转化为特征向量矩阵。
        """
        self.feature_matrix = self.vectorizer.fit_transform(documents)
        return self.feature_matrix

    def find_top_n_similar(self, target_vector: csr_matrix, n: int = 10) -> Tuple[List[int], List[float]]:
        """
        在已有的特征矩阵中，查找与目标向量最相似的前 N 个向量。
        """
        if self.feature_matrix is None:
            raise ValueError("特征矩阵尚未被计算，请先调用 vectorize_documents。")

        sim_scores = cosine_similarity(target_vector, self.feature_matrix).flatten()
        num_docs = self.feature_matrix.shape[0]
        k = min(n + 1, num_docs)
        
        if k <= 1 and num_docs > 0:
             return [], []

        top_indices = np.argpartition(sim_scores, -k)[-k:]
        top_indices = [i for i in top_indices if sim_scores[i] < 0.99999]
        sorted_indices = sorted(top_indices, key=lambda i: sim_scores[i], reverse=True)
        
        final_indices = sorted_indices[:n]
        final_scores = [sim_scores[i] for i in final_indices]

        return final_indices, final_scores

    def save_model(self, file_path: str) -> None:
        """
        将训练好的TF-IDF向量化器序列化到磁盘。
        """
        with open(file_path, 'wb') as f:
            pickle.dump(self.vectorizer, f)

    def load_model(self, file_path: str) -> None:
        """
        从磁盘加载之前保存的TF-IDF向量化器。
        """
        with open(file_path, 'rb') as f:
            self.vectorizer = pickle.load(f)
