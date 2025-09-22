# -*- coding: utf-8 -*-
"""
文件聚类引擎模块 (v3.0.1 - 修正空目录清理逻辑)。

此版本修复了 _remove_empty_subdirectories 方法中的一个 Bug，
确保所有层级的空目录都能被正确地递归删除。
"""

import logging
import os
import json
import shutil
from collections import defaultdict
from typing import List, Callable

import numpy as np
from scipy.sparse import vstack, csr_matrix
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Document
from qzen_core.similarity_engine import SimilarityEngine

# 定义一个无操作的回调函数作为默认值
def _noop_callback(*args, **kwargs):
    pass

def _json_to_vector(json_str: str) -> csr_matrix:
    """将 JSON 字符串反序列化为稀疏矩阵 (CSR Matrix)。"""
    data = json.loads(json_str)
    return csr_matrix((data['data'], data['indices'], data['indptr']), shape=data['shape'])


class ClusterEngine:
    """
    封装了 v3.0 的多轮次聚类算法。
    """

    def __init__(self, db_handler: DatabaseHandler, sim_engine: SimilarityEngine):
        """
        初始化聚类引擎。
        """
        self.db_handler = db_handler
        self.sim_engine = sim_engine

    def run_clustering(self, target_dir: str, k: int, similarity_threshold: float, 
                       progress_callback: Callable = _noop_callback, 
                       is_cancelled_callback: Callable[[], bool] = lambda: False) -> None:
        """
        在指定目录上执行一轮完整的“K-Means + 相似度”聚类，并自动清理空目录。
        """
        logging.info(f"--- 开始对目录 '{target_dir}' 执行新一轮聚类 (K={k}) ---")
        try:
            docs = self._get_documents_from_db(target_dir)
            if len(docs) < k:
                logging.warning(f"目录中的文档总数 ({len(docs)}) 小于 K值 ({k})，无法执行 K-Means 聚类。")
                return

            if is_cancelled_callback(): return

            kmeans_folders = self._perform_kmeans_and_move(docs, target_dir, k, progress_callback, is_cancelled_callback)
            if not kmeans_folders or is_cancelled_callback(): return

            total_kmeans_folders = len(kmeans_folders)
            for i, folder_path in enumerate(kmeans_folders):
                if is_cancelled_callback(): return
                progress_callback(i + 1, total_kmeans_folders, f"正在处理子文件夹: {os.path.basename(folder_path)}")
                self._perform_similarity_grouping_and_move(folder_path, similarity_threshold, is_cancelled_callback)
            
            logging.info(f"--- 目录 '{target_dir}' 的本轮聚类已完成 ---")

            # v3.0 新增：聚类后自动清理空文件夹
            if not is_cancelled_callback():
                self._remove_empty_subdirectories(target_dir)

        except InterruptedError:
            logging.warning(f"聚类任务在处理目录 '{target_dir}' 时被用户取消。")
        except Exception as e:
            logging.error(f"执行聚类时发生未知错误: {e}", exc_info=True)

    def _get_documents_from_db(self, target_dir: str) -> List[Document]:
        """从数据库中获取指定目录下的所有文档记录。"""
        with self.db_handler.get_session() as session:
            normalized_path = os.path.normpath(target_dir)
            path_pattern = os.path.join(normalized_path, '') + '%'
            return session.query(Document).filter(Document.file_path.like(path_pattern)).all()

    def _perform_kmeans_and_move(self, docs: List[Document], base_dir: str, k: int, progress_callback: Callable, is_cancelled_callback: Callable[[], bool]) -> List[str]:
        """
        执行 K-Means 聚类并移动文件，支持进度与取消。
        """
        valid_docs = [doc for doc in docs if doc.feature_vector]
        if len(valid_docs) < len(docs):
            logging.warning(f"在 K-Means 宏观分类中，跳过了 {len(docs) - len(valid_docs)} 个没有有效特征向量的文档。")
        
        if len(valid_docs) < k:
            logging.warning(f"过滤后，目录中的有效文档数量 ({len(valid_docs)}) 小于 K值 ({k})，无法执行 K-Means 聚类。")
            return []

        feature_vectors = [_json_to_vector(doc.feature_vector) for doc in valid_docs]
        feature_matrix = vstack(feature_vectors)

        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(feature_matrix)
        labels = kmeans.labels_

        clustered_docs = defaultdict(list)
        for doc, label in zip(valid_docs, labels):
            clustered_docs[label].append(doc)

        created_folders, docs_to_update = [], []
        total_clusters = len(clustered_docs)
        for i, (label, doc_list) in enumerate(clustered_docs.items()):
            if is_cancelled_callback(): raise InterruptedError("任务已取消")
            progress_callback(i + 1, total_clusters, f"K-Means 分类: 正在移动第 {i+1} 簇")

            new_folder_path = os.path.normpath(os.path.join(base_dir, str(label)))
            os.makedirs(new_folder_path, exist_ok=True)
            created_folders.append(new_folder_path)

            for doc in doc_list:
                original_path = doc.file_path
                new_path = os.path.normpath(os.path.join(new_folder_path, os.path.basename(original_path)))
                doc.file_path = new_path
                docs_to_update.append(doc)
                shutil.move(original_path, new_path)
        
        if docs_to_update: self.db_handler.bulk_update_documents(docs_to_update)
        return created_folders

    def _perform_similarity_grouping_and_move(self, folder_path: str, threshold: float, is_cancelled_callback: Callable[[], bool]) -> None:
        """
        在单个文件夹内执行相似度分组，支持取消。
        """
        docs = self._get_documents_from_db(folder_path)
        if len(docs) <= 1: return

        valid_docs = [doc for doc in docs if doc.feature_vector]
        if len(valid_docs) < len(docs):
            logging.warning(f"在相似文件微观分组中，跳过了 {len(docs) - len(valid_docs)} 个没有有效特征向量的文档。")

        if len(valid_docs) <= 1: return

        feature_vectors = [_json_to_vector(doc.feature_vector) for doc in valid_docs]
        feature_matrix = vstack(feature_vectors)
        content_slices = [doc.content_slice for doc in valid_docs]

        clusters_indices = self._cluster_documents_by_similarity(feature_matrix, threshold)
        if not clusters_indices: return

        docs_to_update = []
        for cluster in clusters_indices:
            if is_cancelled_callback(): raise InterruptedError("任务已取消")
            cluster_docs = [valid_docs[i] for i in cluster]
            cluster_content = [content_slices[i] for i in cluster]

            topic_name = self._extract_topic_keywords(cluster_content) or "相似文件簇"
            topic_folder_path = os.path.normpath(os.path.join(folder_path, topic_name))
            os.makedirs(topic_folder_path, exist_ok=True)

            for doc in cluster_docs:
                original_path = doc.file_path
                new_path = os.path.normpath(os.path.join(topic_folder_path, os.path.basename(original_path)))
                doc.file_path = new_path
                docs_to_update.append(doc)
                shutil.move(original_path, new_path)

        if docs_to_update: self.db_handler.bulk_update_documents(docs_to_update)

    def _cluster_documents_by_similarity(self, feature_matrix: csr_matrix, similarity_threshold: float) -> List[List[int]]:
        num_docs = feature_matrix.shape[0]
        sim_matrix = cosine_similarity(feature_matrix)
        clustered = [False] * num_docs
        clusters = []
        for i in range(num_docs):
            if clustered[i]: continue
            current_cluster = [i]
            clustered[i] = True
            for j in range(i + 1, num_docs):
                if not clustered[j] and sim_matrix[i, j] >= similarity_threshold:
                    current_cluster.append(j)
                    clustered[j] = True
            if len(current_cluster) > 1:
                clusters.append(current_cluster)
        return clusters

    def _extract_topic_keywords(self, content_list: List[str], top_n: int = 3) -> str:
        if not content_list: return ""
        try:
            tfidf_matrix = self.sim_engine.vectorizer.transform(content_list)
            summed_tfidf = np.array(tfidf_matrix.sum(axis=0)).flatten()
            feature_names = np.array(self.sim_engine.vectorizer.get_feature_names_out())
            top_indices = summed_tfidf.argsort()[-top_n:][::-1]
            keywords = [feature_names[i] for i in top_indices]
            return "_".join(keywords)
        except Exception as e:
            logging.error(f"提取主题关键词时出错: {e}")
            return ""

    def _remove_empty_subdirectories(self, path: str) -> None:
        """
        从底向上递归删除指定路径下的所有空子文件夹。

        Args:
            path: 开始扫描的根目录。
        """
        logging.info(f"开始清理目录 '{path}' 下的空文件夹...")
        removed_count = 0
        # 从底向上遍历，这样可以先删除子目录再判断父目录是否为空
        for dirpath, _, _ in os.walk(path, topdown=False):
            # v3.0.1 修正: 不再依赖 os.walk 提供的 dirnames/filenames 列表，
            # 因为它们是遍历开始前的快照。在每次循环中，我们必须用 os.listdir 
            # 重新检查当前目录是否真的为空，以确保逻辑的正确性。
            if not os.listdir(dirpath):
                try:
                    os.rmdir(dirpath)
                    logging.info(f"  - 已删除空文件夹: {dirpath}")
                    removed_count += 1
                except OSError as e:
                    logging.error(f"无法删除空文件夹 {dirpath}: {e}")
        logging.info(f"空文件夹清理完成，共删除 {removed_count} 个目录。")
