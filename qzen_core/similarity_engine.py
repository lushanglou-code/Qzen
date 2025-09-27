# -*- coding: utf-8 -*-
"""
相似度计算引擎模块 (v4.3.0 - 优化向量化器配置)。

此版本修复了 `TfidfVectorizer` 初始化时产生的 `UserWarning`。
通过在自定义分词器 `_tokenizer` 中统一处理停用词，并从 `TfidfVectorizer`
的参数中移除 `stop_words`，解决了停用词处理不一致的警告，确保了
停用词逻辑的唯一性和清晰性。
"""

import logging
from typing import List, Tuple

import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --- 内置停用词 ---
BUILTIN_STOPWORDS = set([
    "的", "一", "不", "在", "人", "有", "是", "为", "以", "于", "上", "他", "而",
    "后", "之", "来", "及", "了", "因", "下", "可", "到", "由", "这", "与", "也",
    "此", "但", "并", "得", "其", "我们", "你", "他们", "一个", "一些", "和",
    "或", "等", "地", "中", "对", "从", "到", "我", "她"
])


class SimilarityEngine:
    """
    封装了所有与文本向量化和相似度计算相关的逻辑。
    """

    def __init__(self, max_features: int = 5000, custom_stopwords: List[str] = None):
        """
        初始化 SimilarityEngine。
        """
        self.max_features = max_features
        self.stopwords = self._load_stopwords(custom_stopwords)
        # v4.3.0 修复: 移除 stop_words 参数，因为 _tokenizer 已处理停用词，
        # 这可以解决 'Your stop_words may be inconsistent' 的 UserWarning。
        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            tokenizer=self._tokenizer
        )
        self.feature_matrix = None
        self.doc_map = []

    def _load_stopwords(self, custom_stopwords: List[str] = None) -> set:
        """加载停用词。"""
        stopwords = BUILTIN_STOPWORDS.copy()
        if custom_stopwords:
            stopwords.update(custom_stopwords)
        return stopwords

    def update_stopwords(self, custom_stopwords: List[str]):
        """动态更新停用词列表并重建向量化器。"""
        self.stopwords = self._load_stopwords(custom_stopwords)
        # v4.3.0 修复: 同样在此处移除 stop_words 参数
        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            tokenizer=self._tokenizer
        )
        logging.info("SimilarityEngine 已接收新的停用词并重建了 TF-IDF 向量化器。")

    def _tokenizer(self, text: str) -> List[str]:
        """
        自定义分词器，使用 jieba 分词并过滤停用词。
        """
        # 在分词时直接过滤停用词和空字符串
        return [word for word in jieba.cut(text) if word.strip() and word not in self.stopwords]

    def vectorize_documents(self, documents: List[str]):
        """将文档列表转换为 TF-IDF 特征矩阵。"""
        if not documents:
            return None
        return self.vectorizer.fit_transform(documents)

    def find_top_n_similar(self, target_vector, n: int = 5) -> Tuple[List[int], List[float]]:
        """在特征矩阵中查找与目标向量最相似的 N 个向量。"""
        if self.feature_matrix is None:
            return [], []

        cosine_similarities = cosine_similarity(target_vector, self.feature_matrix).flatten()
        # 使用 argpartition 高效查找 top N，避免对整个数组排序
        # 我们需要 N+1 个，因为最相似的总是它自己
        n_plus_one = min(n + 1, len(cosine_similarities))
        top_indices = np.argpartition(cosine_similarities, -n_plus_one)[-n_plus_one:]

        # 过滤掉自身
        top_indices = [i for i in top_indices if cosine_similarities[i] < 0.9999]

        # 按分数排序
        sorted_indices = sorted(top_indices, key=lambda i: cosine_similarities[i], reverse=True)

        top_n_indices = sorted_indices[:n]
        top_n_scores = [cosine_similarities[i] for i in top_n_indices]

        return top_n_indices, top_n_scores

    def get_top_keywords(self, doc_indices: List[int], n: int = 5) -> str:
        """
        v4.2.6 修复: 为给定的文档索引列表提取最具代表性的关键词。
        """
        if self.feature_matrix is None:
            raise NotFittedError("The TF-IDF vectorizer is not fitted")

        # 合并指定文档的向量
        combined_vector = np.sum(self.feature_matrix[doc_indices], axis=0)

        # 转换为 (1, n_features) 的稠密数组
        combined_vector = np.asarray(combined_vector).flatten()

        # 获取特征词（关键词）列表
        feature_names = self.vectorizer.get_feature_names_out()

        # 找到分数最高的 N 个词的索引
        # 使用 argpartition 避免完全排序
        n_keywords = min(n, len(feature_names))
        if n_keywords == 0:
            return "无有效关键词"

        top_indices = np.argpartition(combined_vector, -n_keywords)[-n_keywords:]

        # 按分数排序并获取关键词
        sorted_indices = sorted(top_indices, key=lambda i: combined_vector[i], reverse=True)

        top_keywords = [feature_names[i] for i in sorted_indices]

        return "_".join(top_keywords)
