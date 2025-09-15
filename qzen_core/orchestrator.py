# -*- coding: utf-8 -*-
"""
业务流程协调器模块。

定义了 Orchestrator 类，作为业务逻辑层的“总指挥”，负责协调
数据访问层和各个业务引擎，以完成一个完整的用户请求流程。
"""

import logging
import os
import json
import shutil
from typing import Callable, List, Tuple, Set

import numpy as np
from scipy.sparse import vstack, csr_matrix

from qzen_data import file_handler, database_handler
from qzen_data.models import Document
from qzen_core.similarity_engine import SimilarityEngine
from qzen_core.cluster_engine import ClusterEngine, find_longest_common_prefix


def _vector_to_json(vector: csr_matrix) -> str:
    return json.dumps({
        'data': vector.data.tolist(),
        'indices': vector.indices.tolist(),
        'indptr': vector.indptr.tolist(),
        'shape': vector.shape
    })


def _json_to_vector(json_str: str) -> csr_matrix:
    data = json.loads(json_str)
    return csr_matrix((data['data'], data['indices'], data['indptr']), shape=data['shape'])


class Orchestrator:
    """
    协调各个模块以完成复杂的业务流程。
    """
    def __init__(self, db_handler: database_handler.DatabaseHandler):
        self.db_handler = db_handler
        self.similarity_engine = SimilarityEngine()
        self.cluster_engine = ClusterEngine()
        self._is_engine_primed: bool = False
        self._doc_path_map: List[str] = []

    def prepare_deduplication_workspace(self, intermediate_path: str) -> None:
        """准备去重任务的工作空间（在主线程中执行）。"""
        logging.info("--- 准备全新的去重任务工作空间 ---")
        logging.info("正在清空并重建数据库表...")
        self.db_handler.recreate_tables()
        logging.info("数据库表已清空并重建。")

        logging.info("正在清空中间文件夹...")
        if os.path.exists(intermediate_path):
            try:
                shutil.rmtree(intermediate_path)
                logging.info(f"已删除旧的中间文件夹: {intermediate_path}")
            except OSError as e:
                logging.error(f"无法删除中间文件夹: {e}")
                raise
        os.makedirs(intermediate_path, exist_ok=True)
        logging.info(f"已创建新的中间文件夹: {intermediate_path}")

    def run_deduplication_core(self, source_path: str, intermediate_path: str, allowed_extensions: set[str], progress_callback: Callable[[int, int, str], None]) -> None:
        """执行核心的去重与文件复制逻辑（在后台线程中执行）。"""
        logging.info("--- 开始核心去重扫描与复制任务 ---")
        files_to_scan = list(file_handler.scan_files(source_path, allowed_extensions))
        total_files = len(files_to_scan)
        processed_hashes = set()
        new_docs_to_save = []

        for i, file_path in enumerate(files_to_scan):
            base_name = os.path.basename(file_path)
            progress_callback(i + 1, total_files, f"扫描文件: {base_name}")
            file_hash = file_handler.calculate_file_hash(file_path)

            if file_hash and file_hash not in processed_hashes:
                processed_hashes.add(file_hash)
                destination_path = os.path.normpath(os.path.join(intermediate_path, os.path.relpath(file_path, source_path)))
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                shutil.copy2(file_path, destination_path)
                new_doc = Document(file_hash=file_hash, file_path=destination_path, feature_vector=None)
                new_docs_to_save.append(new_doc)

        if new_docs_to_save:
            logging.info(f"向数据库中批量插入 {len(new_docs_to_save)} 个新文档记录。")
            self.db_handler.bulk_insert_documents(new_docs_to_save)
        
        self._is_engine_primed = False
        progress_callback(total_files, total_files, "去重任务完成！")
        logging.info("--- 核心去重任务结束 ---")

    def run_vectorization(self, progress_callback: Callable[[int, int, str], None]) -> None:
        # ... (此方法及后续方法保持不变) ...
        logging.info("开始文档向量化流程。")
        docs_to_vectorize = self.db_handler.get_documents_without_vectors()
        total_docs = len(docs_to_vectorize)
        if not docs_to_vectorize:
            progress_callback(1, 1, "所有文档均已向量化，无需操作。")
            return
        content_slices = [file_handler.get_content_slice(doc.file_path) for doc in docs_to_vectorize]
        progress_callback(0, total_docs, "正在计算TF-IDF特征向量...")
        feature_matrix = self.similarity_engine.vectorize_documents(content_slices)
        for i, doc in enumerate(docs_to_vectorize):
            progress_callback(i + 1, total_docs, f"准备向量: {os.path.basename(doc.file_path)}")
            doc.feature_vector = _vector_to_json(feature_matrix[i])
        logging.info(f"正在向数据库中批量更新 {len(docs_to_vectorize)} 个文档的特征向量。")
        self.db_handler.bulk_update_documents(docs_to_vectorize)
        self._is_engine_primed = False
        progress_callback(total_docs, total_docs, "向量化完成！")
        logging.info("文档向量化流程结束。")

    def prime_similarity_engine(self, force_reload: bool = False) -> None:
        if self._is_engine_primed and not force_reload:
            return
        logging.info("正在预热相似度引擎...")
        all_docs = self.db_handler.get_all_documents()
        docs_with_vectors = [doc for doc in all_docs if doc.feature_vector]
        if not docs_with_vectors:
            logging.warning("数据库中没有可用的特征向量，引擎无法预热。")
            self.similarity_engine.feature_matrix = None
            self._doc_path_map = []
            self._is_engine_primed = True
            return
        vectors = []
        doc_paths = []
        for doc in docs_with_vectors:
            try:
                vectors.append(_json_to_vector(doc.feature_vector))
                doc_paths.append(doc.file_path)
            except (json.JSONDecodeError, KeyError) as e:
                logging.error(f"无法解析文件 '{doc.file_path}' 的特征向量JSON。该向量可能已损坏或格式不兼容。将跳过此文件。错误: {e}")
        if not vectors:
            logging.error("没有成功加载任何有效的特征向量。")
            self.similarity_engine.feature_matrix = None
        else:
            self.similarity_engine.feature_matrix = vstack(vectors)
        self._doc_path_map = doc_paths
        self._is_engine_primed = True
        logging.info(f"相似度引擎预热完成，加载了 {len(self._doc_path_map)} 个向量。")

    def find_top_n_similar_for_file(self, target_file_path: str, n: int) -> List[Tuple[str, float]]:
        self.prime_similarity_engine()
        if not self._is_engine_primed or self.similarity_engine.feature_matrix is None:
            return []
        try:
            target_index = self._doc_path_map.index(os.path.normpath(target_file_path))
        except ValueError:
            logging.error(f"目标文件 '{target_file_path}' 不在已知的文档列表中。")
            return []
        target_vector = self.similarity_engine.feature_matrix[target_index]
        indices, scores = self.similarity_engine.find_top_n_similar(target_vector, n=n)
        return [(self._doc_path_map[i], score) for i, score in zip(indices, scores)]

    def run_clustering_and_renaming(self, target_path: str, similarity_threshold: float, progress_callback: Callable[[int, int, str], None]) -> str:
        self.prime_similarity_engine()
        if self.similarity_engine.feature_matrix is None or self.similarity_engine.feature_matrix.shape[0] == 0:
            return "没有可供聚类的文档。"
        clusters = self.cluster_engine.cluster_documents(self.similarity_engine.feature_matrix, similarity_threshold)
        if not clusters:
            return "在当前相似度阈值下，没有找到可以构成簇的相似文档。"
        os.makedirs(target_path, exist_ok=True)
        total_clusters = len(clusters)
        total_files_processed = 0
        for i, cluster_indices in enumerate(clusters):
            progress_callback(i + 1, total_clusters, f"正在处理第 {i+1} 个文件簇...")
            original_paths = [self._doc_path_map[idx] for idx in cluster_indices]
            original_filenames = [os.path.basename(p) for p in original_paths]
            cluster_prefix = find_longest_common_prefix(original_filenames).strip()
            if len(cluster_prefix) < 3: cluster_prefix = f"相似文件簇_{i+1}"
            cluster_dir = os.path.join(target_path, cluster_prefix)
            os.makedirs(cluster_dir, exist_ok=True)
            for j, original_path in enumerate(original_paths):
                _, extension = os.path.splitext(original_path)
                new_filename = f"{cluster_prefix}_{j+1}{extension}"
                destination_path = os.path.join(cluster_dir, new_filename)
                shutil.copy2(original_path, destination_path)
            total_files_processed += len(cluster_indices)
        summary = f"聚类完成！共创建 {total_clusters} 个簇，整理了 {total_files_processed} 个文件。"
        logging.info(summary)
        return summary

    def run_filename_search(self, keyword: str, intermediate_path: str, target_path: str, allowed_extensions: Set[str], progress_callback: Callable[[int, int, str], None]) -> str:
        logging.info(f"开始按文件名搜索，关键词: '{keyword}'")
        files_to_scan = list(file_handler.scan_files(intermediate_path, allowed_extensions))
        if not files_to_scan: return "中间文件夹中没有可供搜索的文件。"
        matched_files = [p for p in files_to_scan if keyword.lower() in os.path.basename(p).lower()]
        if not matched_files: return f"没有找到文件名包含 '{keyword}' 的文件。"
        destination_dir = os.path.join(target_path, f"文件名包含_{keyword}")
        os.makedirs(destination_dir, exist_ok=True)
        total_files = len(matched_files)
        for i, file_path in enumerate(matched_files):
            progress_callback(i + 1, total_files, f"正在复制: {os.path.basename(file_path)}")
            shutil.copy2(file_path, destination_dir)
        summary = f"文件名搜索完成！共找到并复制了 {total_files} 个文件。"
        logging.info(summary)
        return summary

    def run_content_search(self, keyword: str, target_path: str, progress_callback: Callable[[int, int, str], None]) -> str:
        logging.info(f"开始按文件内容搜索，关键词: '{keyword}'")
        all_docs = self.db_handler.get_all_documents()
        if not all_docs: return "数据库中没有可供搜索的文档记录。"
        matched_docs = []
        total_docs = len(all_docs)
        for i, doc in enumerate(all_docs):
            progress_callback(i + 1, total_docs, f"正在扫描: {os.path.basename(doc.file_path)}")
            content_slice = file_handler.get_content_slice(doc.file_path)
            if keyword.lower() in content_slice.lower():
                matched_docs.append(doc)
        if not matched_docs: return f"没有找到内容包含 '{keyword}' 的文件。"
        destination_dir = os.path.join(target_path, f"内容包含_{keyword}")
        os.makedirs(destination_dir, exist_ok=True)
        total_files = len(matched_docs)
        for i, doc in enumerate(matched_docs):
            progress_callback(i + 1, total_files, f"正在复制: {os.path.basename(doc.file_path)}")
            shutil.copy2(doc.file_path, destination_dir)
        summary = f"文件内容搜索完成！共找到并复制了 {total_files} 个文件。"
        logging.info(summary)
        return summary
