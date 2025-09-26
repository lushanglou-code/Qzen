# -*- coding: utf-8 -*-
"""
聚类引擎模块 (v5.4.1 - 健壮性修复)。

此版本修复了 `_cleanup_empty_folders` 方法中的一个逻辑缺陷。
原先的实现依赖于 `os.walk` 的静态 `dirnames` 和 `filenames` 列表，
这在子目录被删除后无法正确判断父目录是否变为空。

新实现改用 `os.listdir()` 在循环内部进行实时检查，确保了空目录
删除的准确性和健壮性。
"""
import logging
import os
import shutil
from collections import defaultdict
from typing import List, Callable

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.exceptions import NotFittedError

from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Document, RenameResult
from qzen_core.similarity_engine import SimilarityEngine


def _noop_callback(*args, **kwargs):
    pass


def _find_unique_filepath(file_path: str) -> str:
    """
    如果文件路径已存在，则为其生成一个唯一的新路径。
    例如：'C:\\path\\file.txt' -> 'C:\\path\\file (1).txt'
    """
    if not os.path.exists(file_path):
        return file_path

    directory, filename = os.path.split(file_path)
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_filename = f"{name} ({counter}){ext}"
        new_path = os.path.join(directory, new_filename)
        if not os.path.exists(new_path):
            return new_path
        counter += 1


class ClusterEngine:
    """
    封装了所有与文档聚类和文件系统操作相关的逻辑。
    """

    def __init__(self, db_handler: DatabaseHandler, similarity_engine: SimilarityEngine):
        self.db_handler = db_handler
        self.similarity_engine = similarity_engine

    def _get_docs_in_dir(self, target_dir: str) -> List[Document]:
        """
        获取指定目录下所有已入库的文档。
        """
        native_target_dir = os.path.normpath(target_dir)
        if not native_target_dir.endswith(os.path.sep):
            native_target_dir += os.path.sep

        all_docs = self.db_handler.get_all_documents()
        normalized_query_path = native_target_dir.replace('\\', '/')

        docs_in_dir = [
            doc for doc in all_docs
            if doc.file_path.replace('\\', '/').startswith(normalized_query_path)
        ]
        logging.info(f"主查询完成，使用 startswith('{normalized_query_path}') 找到了 {len(docs_in_dir)} 个匹配的文档。")
        return docs_in_dir

    def _get_top_keywords(self, doc_indices: List[int]) -> str:
        """
        为给定的文档索引列表提取最具代表性的关键词。
        """
        try:
            return self.similarity_engine.get_top_keywords(doc_indices)
        except NotFittedError:
            logging.error("提取主题关键词时出错: The TF-IDF vectorizer is not fitted")
            return "无法提取关键词"
        except Exception as e:
            logging.error(f"提取主题关键词时发生未知错误: {e}", exc_info=True)
            return "无法提取关键词"

    def _move_files_to_cluster_dir(self, docs: List[Document], base_dir: str, cluster_name: str,
                                   progress_callback: Callable, is_cancelled: Callable) -> int:
        """
        将文档移动到指定的聚类子目录中。
        """
        cluster_dir = os.path.join(base_dir, cluster_name)
        os.makedirs(cluster_dir, exist_ok=True)
        moved_count = 0

        for i, doc in enumerate(docs):
            if is_cancelled(): return moved_count
            progress_callback(i + 1, len(docs), f"正在移动文件到: {cluster_name}")

            source_path = os.path.normpath(doc.file_path)

            if os.path.exists(source_path):
                try:
                    base_filename = os.path.basename(source_path)
                    destination_path = os.path.join(cluster_dir, base_filename)
                    final_destination_path = _find_unique_filepath(destination_path)

                    shutil.move(source_path, final_destination_path)
                    moved_count += 1

                    with self.db_handler.get_session() as session:
                        doc_to_update = session.get(Document, doc.id)
                        if doc_to_update:
                            doc_to_update.file_path = final_destination_path.replace('\\', '/')
                            session.commit()
                            logging.info(f"数据库已更新: ID {doc_to_update.id} 的路径已变更为 '{doc_to_update.file_path}'")
                        else:
                            logging.warning(f"尝试更新一个不存在的文档 (ID: {doc.id})，已跳过。")

                    if final_destination_path != destination_path:
                        logging.warning(
                            f"目标文件已存在，已自动重命名: '{destination_path}' -> '{final_destination_path}'")

                except Exception as e:
                    logging.error(f"移动文件 {source_path} 到 {cluster_dir} 时失败: {e}", exc_info=True)
            else:
                logging.warning(f"文件在移动前未找到，可能已被前序操作移动。已跳过: {source_path}")
        return moved_count

    def _cleanup_empty_folders(self, directory: str):
        """
        从底向上递归删除指定目录下的所有空文件夹。
        """
        logging.info(f"开始清理目录 '{directory}' 下的空文件夹...")
        deleted_count = 0
        for dirpath, _, _ in os.walk(directory, topdown=False):
            # v5.4.1 修复: 不依赖 os.walk 的静态列表，改用 os.listdir 进行实时检查
            if not os.listdir(dirpath):
                try:
                    os.rmdir(dirpath)
                    logging.info(f"  - 已删除空文件夹: {dirpath}")
                    deleted_count += 1
                except OSError as e:
                    logging.error(f"删除空文件夹 {dirpath} 时出错: {e}")
        logging.info(f"空文件夹清理完成，共删除 {deleted_count} 个目录。")

    def run_kmeans_clustering(self, target_dir: str, k: int, progress_callback: Callable,
                              is_cancelled_callback: Callable) -> bool:
        """
        对指定目录下的文档执行 K-Means 聚类。
        """
        logging.info(f"--- 开始对目录 '{target_dir}' 执行 K-Means 聚类 (K={k}) ---")
        docs_in_dir = self._get_docs_in_dir(target_dir)
        if not docs_in_dir:
            logging.warning("在指定目录中未找到任何已入库的文档，K-Means 操作已跳过。")
            return False

        doc_map = self.similarity_engine.doc_map
        feature_matrix = self.similarity_engine.feature_matrix

        dir_doc_ids = {doc.id for doc in docs_in_dir}
        dir_indices = [i for i, doc in enumerate(doc_map) if doc['id'] in dir_doc_ids]

        if not dir_indices:
            logging.warning("数据库与引擎的文档映射不一致，无法为指定目录筛选出特征向量。")
            return False

        dir_feature_matrix = feature_matrix[dir_indices]
        dir_doc_map = [doc_map[i] for i in dir_indices]

        kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
        kmeans.fit(dir_feature_matrix)

        clusters = defaultdict(list)
        for i, label in enumerate(kmeans.labels_):
            clusters[label].append(dir_doc_map[i])

        total_moved = 0
        for label, clustered_docs_info in clusters.items():
            if is_cancelled_callback(): return False

            doc_ids = [info['id'] for info in clustered_docs_info]
            docs_to_move = self.db_handler.get_documents_by_ids(doc_ids)

            cluster_name = f"{label}"
            total_moved += self._move_files_to_cluster_dir(docs_to_move, target_dir, cluster_name, progress_callback,
                                                           is_cancelled_callback)

        self._cleanup_empty_folders(target_dir)
        logging.info(f"K-Means 聚类完成。共处理 {len(dir_doc_map)} 个文件，分为 {k} 个簇。")
        return True

    def run_similarity_clustering(self, target_dir: str, threshold: float, progress_callback: Callable,
                                  is_cancelled_callback: Callable) -> bool:
        """
        对指定目录下的文档执行基于余弦相似度的分组。
        """
        logging.info(f"--- 开始对目录 '{target_dir}' 执行相似度分组 (阈值={threshold}) ---")
        docs_in_dir = self._get_docs_in_dir(target_dir)
        if not docs_in_dir:
            logging.warning("在指定目录中未找到任何已入库的文档，相似度分组操作已跳过。")
            return False

        doc_map = self.similarity_engine.doc_map
        feature_matrix = self.similarity_engine.feature_matrix

        dir_doc_ids = {doc.id for doc in docs_in_dir}
        dir_indices = [i for i, doc in enumerate(doc_map) if doc['id'] in dir_doc_ids]

        if not dir_indices:
            logging.warning("数据库与引擎的文档映射不一致，无法为指定目录筛选出特征向量。")
            return False

        dir_feature_matrix = feature_matrix[dir_indices]
        dir_doc_map = [doc_map[i] for i in dir_indices]

        similarity_matrix = cosine_similarity(dir_feature_matrix)

        visited = [False] * len(dir_doc_map)
        clusters = []
        for i in range(len(dir_doc_map)):
            if visited[i]:
                continue

            current_cluster_indices = [i]
            for j in range(i + 1, len(dir_doc_map)):
                if similarity_matrix[i, j] >= threshold:
                    current_cluster_indices.append(j)

            if len(current_cluster_indices) > 1:
                clusters.append(current_cluster_indices)
                for idx in current_cluster_indices:
                    visited[idx] = True

        # --- 移动相似文件簇 ---
        if clusters:
            total_moved = 0
            for i, cluster_indices in enumerate(clusters):
                if is_cancelled_callback(): return False

                doc_ids = [dir_doc_map[idx]['id'] for idx in cluster_indices]
                docs_to_move = self.db_handler.get_documents_by_ids(doc_ids)

                top_keywords = self._get_top_keywords(cluster_indices)
                cluster_name = f"相似文件簇/{i:02d}_{top_keywords}"

                total_moved += self._move_files_to_cluster_dir(docs_to_move, target_dir, cluster_name, progress_callback,
                                                               is_cancelled_callback)
            logging.info(f"相似度分组完成。共找到 {total_moved} 个文件被归入新簇。")
        else:
            logging.info("在给定的阈值下，未发现任何可以归为一类的相似文件。")

        # --- v5.4 新增: 移动所有未成簇的独立文件到 'alone' 文件夹 ---
        alone_doc_indices = [i for i, is_visited in enumerate(visited) if not is_visited]
        if alone_doc_indices:
            if is_cancelled_callback(): return False
            logging.info(f"找到 {len(alone_doc_indices)} 个未成簇的独立文件，将它们移动到 'alone' 文件夹。")
            alone_doc_ids = [dir_doc_map[idx]['id'] for idx in alone_doc_indices]
            docs_to_move_alone = self.db_handler.get_documents_by_ids(alone_doc_ids)
            self._move_files_to_cluster_dir(docs_to_move_alone, target_dir, "alone", progress_callback, is_cancelled_callback)

        self._cleanup_empty_folders(target_dir)
        logging.info(f"相似度分组操作已全部完成。")
        return True
