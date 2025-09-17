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
from typing import Callable, List, Tuple, Set, Dict

import numpy as np
from scipy.sparse import vstack, csr_matrix

from qzen_data import file_handler, database_handler
from qzen_data.models import Document, DeduplicationResult, RenameResult, SearchResult
from qzen_core.similarity_engine import SimilarityEngine
from qzen_core.cluster_engine import ClusterEngine, find_longest_common_prefix


def _vector_to_json(vector: csr_matrix) -> str:
    """将稀疏矩阵 (CSR Matrix) 序列化为 JSON 字符串。"""
    return json.dumps({
        'data': vector.data.tolist(),
        'indices': vector.indices.tolist(),
        'indptr': vector.indptr.tolist(),
        'shape': vector.shape
    })


def _json_to_vector(json_str: str) -> csr_matrix:
    """将 JSON 字符串反序列化为稀疏矩阵 (CSR Matrix)。"""
    data = json.loads(json_str)
    return csr_matrix((data['data'], data['indices'], data['indptr']), shape=data['shape'])


class Orchestrator:
    """
    协调各个模块以完成复杂的业务流程。
    """
    def __init__(self, db_handler: database_handler.DatabaseHandler, max_features: int, slice_size_kb: int):
        """
        初始化 Orchestrator。
        """
        self.db_handler = db_handler
        self.max_features = max_features
        self.slice_size_kb = slice_size_kb
        self.similarity_engine = SimilarityEngine(max_features=self.max_features)
        self.cluster_engine = ClusterEngine()
        self._is_engine_primed: bool = False
        self._doc_path_map: List[str] = []

    def prepare_deduplication_workspace(self, intermediate_path: str) -> None:
        """为全新的去重任务准备工作空间。"""
        logging.info("--- 准备全新的去重任务工作空间 ---")
        self.db_handler.recreate_tables()
        if os.path.exists(intermediate_path):
            try:
                shutil.rmtree(intermediate_path)
            except OSError as e:
                logging.error(f"无法删除中间文件夹: {e}")
                raise
        os.makedirs(intermediate_path, exist_ok=True)

    def run_deduplication_core(self, source_path: str, intermediate_path: str, allowed_extensions: Set[str], progress_callback: Callable, is_cancelled_callback: Callable[[], bool] = lambda: False) -> Tuple[str, List[DeduplicationResult]]:
        """执行核心的去重逻辑，并将结果存入数据库。"""
        task_run = self.db_handler.create_task_run(task_type='deduplication')
        files_to_scan = list(file_handler.scan_files(source_path, allowed_extensions))
        total_files, processed_hashes, new_docs_to_save, deduplication_results = len(files_to_scan), {}, [], []

        for i, file_path in enumerate(files_to_scan):
            if is_cancelled_callback():
                logging.info("去重任务被用户取消。")
                return "任务已取消", []
            progress_callback(i + 1, total_files, f"扫描文件: {os.path.basename(file_path)}")
            file_hash = file_handler.calculate_file_hash(file_path)
            if file_hash and file_hash not in processed_hashes:
                processed_hashes[file_hash] = file_path
                destination_path = os.path.normpath(os.path.join(intermediate_path, os.path.relpath(file_path, source_path)))
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                shutil.copy2(file_path, destination_path)
                new_docs_to_save.append(Document(file_hash=file_hash, file_path=destination_path))
            elif file_hash:
                deduplication_results.append(DeduplicationResult(task_run_id=task_run.id, duplicate_file_path=file_path, original_file_hash=file_hash))

        if new_docs_to_save: self.db_handler.bulk_insert_documents(new_docs_to_save)
        if deduplication_results: self.db_handler.bulk_insert_deduplication_results(deduplication_results)
        
        self._is_engine_primed = False
        summary = f"去重任务完成！共找到 {len(deduplication_results)} 个重复文件。"
        summary += " 仅显示前100条，完整结果已存入数据库。" if len(deduplication_results) > 100 else " 详情已存入数据库。"
        self.db_handler.update_task_summary(task_run.id, summary)
        return summary, deduplication_results[:100]

    def run_vectorization(self, progress_callback: Callable, is_cancelled_callback: Callable[[], bool] = lambda: False) -> str:
        """为数据库中尚未处理的文档计算并存储其特征向量。"""
        docs_to_vectorize = self.db_handler.get_documents_without_vectors()
        if not docs_to_vectorize: return "所有文档均已向量化，无需操作。"

        content_slices = [file_handler.get_content_slice(doc.file_path, self.slice_size_kb) for doc in docs_to_vectorize]
        feature_matrix = self.similarity_engine.vectorize_documents(content_slices)
        
        for i, doc in enumerate(docs_to_vectorize):
            if is_cancelled_callback():
                logging.info("向量化任务被用户取消。")
                return "任务已取消"
            progress_callback(i + 1, len(docs_to_vectorize), f"准备向量: {os.path.basename(doc.file_path)}")
            doc.feature_vector = _vector_to_json(feature_matrix[i])
            
        self.db_handler.bulk_update_documents(docs_to_vectorize)
        self._is_engine_primed = False
        return f"向量化任务已成功完成，处理了 {len(docs_to_vectorize)} 个文档。"

    def prime_similarity_engine(self, force_reload: bool = False, is_cancelled_callback: Callable[[], bool] = lambda: False) -> None:
        """预热相似度引擎。"""
        if self._is_engine_primed and not force_reload:
            return
        all_docs = self.db_handler.get_all_documents()
        docs_with_vectors = [doc for doc in all_docs if doc.feature_vector]
        if not docs_with_vectors:
            self.similarity_engine.feature_matrix = None
            self._doc_path_map = []
            self._is_engine_primed = True
            return

        vectors, doc_paths = [], []
        for doc in docs_with_vectors:
            if is_cancelled_callback(): return
            try:
                vectors.append(_json_to_vector(doc.feature_vector))
                doc_paths.append(doc.file_path)
            except (json.JSONDecodeError, KeyError) as e:
                logging.error(f"无法解析文件 '{doc.file_path}' 的特征向量JSON。将跳过此文件。错误: {e}")

        if vectors:
            self.similarity_engine.feature_matrix = vstack(vectors)
        else:
            self.similarity_engine.feature_matrix = None
        self._doc_path_map = doc_paths
        self._is_engine_primed = True

    def find_top_n_similar_for_file(self, target_file_path: str, n: int, is_cancelled_callback: Callable[[], bool] = lambda: False) -> List[Tuple[str, float]]:
        """为指定文件查找最相似的 N 个其他文件。"""
        self.prime_similarity_engine(is_cancelled_callback=is_cancelled_callback)
        if is_cancelled_callback() or not self._is_engine_primed or self.similarity_engine.feature_matrix is None:
            return []
        try:
            target_index = self._doc_path_map.index(os.path.normpath(target_file_path))
        except ValueError:
            return []
        target_vector = self.similarity_engine.feature_matrix[target_index]
        indices, scores = self.similarity_engine.find_top_n_similar(target_vector, n=n)
        return [(self._doc_path_map[i], score) for i, score in zip(indices, scores)]

    def run_clustering_and_renaming(self, target_path: str, similarity_threshold: float, progress_callback: Callable, is_cancelled_callback: Callable[[], bool] = lambda: False) -> Tuple[str, List[RenameResult]]:
        """对所有文档进行自动聚类和重命名，并将结果存入数据库。"""
        self.prime_similarity_engine(is_cancelled_callback=is_cancelled_callback)
        if is_cancelled_callback() or self.similarity_engine.feature_matrix is None or self.similarity_engine.feature_matrix.shape[0] == 0:
            return "没有可供聚类的文档。", []

        task_run = self.db_handler.create_task_run(task_type='rename')
        clusters = self.cluster_engine.cluster_documents(self.similarity_engine.feature_matrix, similarity_threshold)
        if not clusters: return "在当前相似度阈值下，没有找到可以构成簇的相似文档。", []
            
        os.makedirs(target_path, exist_ok=True)
        rename_results = []
        for i, cluster_indices in enumerate(clusters):
            if is_cancelled_callback():
                logging.info("聚类任务被用户取消。")
                return "任务已取消", []
            progress_callback(i + 1, len(clusters), f"正在处理第 {i+1} 个文件簇...")
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
                rename_results.append(RenameResult(task_run_id=task_run.id, original_file_path=original_path, new_file_path=destination_path))

        if rename_results: self.db_handler.bulk_insert_rename_results(rename_results)
        summary = f"聚类完成！共创建 {len(clusters)} 个簇，重命名了 {len(rename_results)} 个文件。"
        summary += " 仅显示前100条，完整结果已存入数据库。" if len(rename_results) > 100 else " 详情已存入数据库。"
        self.db_handler.update_task_summary(task_run.id, summary)
        return summary, rename_results[:100]

    def run_filename_search(self, keyword: str, intermediate_path: str, target_path: str, allowed_extensions: Set[str], progress_callback: Callable, is_cancelled_callback: Callable[[], bool] = lambda: False) -> Tuple[str, List[SearchResult]]:
        """在中间文件夹中按文件名搜索，并将结果存入数据库。"""
        task_run = self.db_handler.create_task_run(task_type='filename_search')
        files_to_scan = list(file_handler.scan_files(intermediate_path, allowed_extensions))
        if not files_to_scan: return "中间文件夹中没有可供搜索的文件。", []
            
        matched_files = [p for p in files_to_scan if keyword.lower() in os.path.basename(p).lower()]
        if not matched_files: return f"没有找到文件名包含 '{keyword}' 的文件。", []

        search_results = [SearchResult(task_run_id=task_run.id, keyword=keyword, matched_file_path=p) for p in matched_files]
        self.db_handler.bulk_insert_search_results(search_results)
            
        destination_dir = os.path.join(target_path, f"文件名包含_{keyword}")
        os.makedirs(destination_dir, exist_ok=True)
        for i, file_path in enumerate(matched_files):
            if is_cancelled_callback():
                logging.info("文件名搜索任务被用户取消。")
                return "任务已取消", []
            progress_callback(i + 1, len(matched_files), f"正在复制: {os.path.basename(file_path)}")
            shutil.copy2(file_path, destination_dir)
            
        summary = f"文件名搜索完成！共找到并复制了 {len(matched_files)} 个文件。"
        summary += " 仅显示前100条，完整结果已存入数据库。" if len(matched_files) > 100 else " 详情已存入数据库。"
        self.db_handler.update_task_summary(task_run.id, summary)
        return summary, search_results[:100]

    def run_content_search(self, keyword: str, target_path: str, progress_callback: Callable, is_cancelled_callback: Callable[[], bool] = lambda: False) -> Tuple[str, List[SearchResult]]:
        """在所有文档的内容切片中搜索关键词，并将结果存入数据库。"""
        task_run = self.db_handler.create_task_run(task_type='content_search')
        all_docs = self.db_handler.get_all_documents()
        if not all_docs: return "数据库中没有可供搜索的文档记录。", []
            
        matched_paths = []
        for i, doc in enumerate(all_docs):
            if is_cancelled_callback():
                logging.info("内容搜索任务被用户取消。")
                return "任务已取消", []
            progress_callback(i + 1, len(all_docs), f"正在扫描: {os.path.basename(doc.file_path)}")
            content_slice = file_handler.get_content_slice(doc.file_path, self.slice_size_kb)
            if keyword.lower() in content_slice.lower():
                matched_paths.append(doc.file_path)
                
        if not matched_paths: return f"没有找到内容包含 '{keyword}' 的文件。", []

        search_results = [SearchResult(task_run_id=task_run.id, keyword=keyword, matched_file_path=p) for p in matched_paths]
        self.db_handler.bulk_insert_search_results(search_results)
            
        destination_dir = os.path.join(target_path, f"内容包含_{keyword}")
        os.makedirs(destination_dir, exist_ok=True)
        for i, file_path in enumerate(matched_paths):
            if is_cancelled_callback():
                logging.info("内容搜索任务被用户取消。")
                return "任务已取消", []
            progress_callback(i + 1, len(matched_paths), f"正在复制: {os.path.basename(file_path)}")
            shutil.copy2(file_path, destination_dir)
            
        summary = f"文件内容搜索完成！共找到并复制了 {len(matched_paths)} 个文件。"
        summary += " 仅显示前100条，完整结果已存入数据库。" if len(matched_paths) > 100 else " 详情已存入数据库。"
        self.db_handler.update_task_summary(task_run.id, summary)
        return summary, search_results[:100]
