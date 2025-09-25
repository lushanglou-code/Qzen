# -*- coding: utf-8 -*-
"""
业务流程协调器模块 (v4.3.1 - 修复引擎预热与数据摄取逻辑)。

此版本包含两个关键修复：
1.  **修复引擎预热逻辑**: 在 `prime_similarity_engine` 中，除了加载预计算的
    特征向量外，还重新加载了文档的内容切片来重新训练 (fit) TF-IDF 模型。
    这彻底解决了在聚类时因模型未训练而导致的 `NotFittedError`。
2.  **修复数据摄取逻辑**: 实现了“扁平化、去重、重命名”策略，确保了
    中间数据源的绝对干净，为所有后续操作提供了可靠的基础。
"""

import logging
import os
import json
import shutil
import stat
import errno
from typing import Callable, List, Tuple, Set, Dict, Any

import numpy as np
from scipy.sparse import vstack, csr_matrix
from sklearn.exceptions import NotFittedError

from qzen_data import file_handler, database_handler
from qzen_data.models import Document, DeduplicationResult, SearchResult
from qzen_core.similarity_engine import SimilarityEngine
from qzen_core.cluster_engine import ClusterEngine


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


def _get_unique_filepath(destination_path: str) -> str:
    """
    v4.3 新增: 检查文件路径是否存在，如果存在，则附加 _dupN 后缀。
    """
    if not os.path.exists(destination_path):
        return destination_path

    directory, filename = os.path.split(destination_path)
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_name = f"{name}_dup{counter}{ext}"
        new_path = os.path.join(directory, new_name)
        if not os.path.exists(new_path):
            logging.warning(f"检测到文件名冲突。原始路径 '{destination_path}' 已存在。将重命名为 '{new_path}'")
            return new_path
        counter += 1

def handle_remove_readonly(func, path, exc_info):
    """
    shutil.rmtree 的错误处理程序，用于处理只读文件导致的权限错误。
    """
    excvalue = exc_info[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise


class Orchestrator:
    """
    协调各个模块以完成复杂的业务流程。
    """

    def __init__(self, db_handler: database_handler.DatabaseHandler, max_features: int, slice_size_kb: int,
                 custom_stopwords: List[str] = None):
        """
        初始化 Orchestrator。
        """
        self.db_handler = db_handler
        self.max_features = max_features
        self.slice_size_kb = slice_size_kb
        self.similarity_engine = SimilarityEngine(
            max_features=self.max_features,
            custom_stopwords=custom_stopwords
        )
        self.cluster_engine = ClusterEngine(self.db_handler, self.similarity_engine)
        self._is_engine_primed: bool = False

    def update_stopwords(self, custom_stopwords: List[str]):
        """
        动态更新相似度引擎中使用的停用词列表。
        """
        if self.similarity_engine:
            self.similarity_engine.update_stopwords(custom_stopwords)
            logging.info("Orchestrator 已将新的停用词列表热更新到 SimilarityEngine。")

    def prepare_deduplication_workspace(self, intermediate_path: str) -> None:
        """为全新的去重任务准备工作空间。"""
        logging.info("--- 准备全新的去重任务工作空间 ---")
        self.db_handler.recreate_tables()
        if os.path.exists(intermediate_path):
            try:
                shutil.rmtree(intermediate_path, onerror=handle_remove_readonly)
            except Exception as e:
                logging.error(f"无法删除中间文件夹: {e}")
                raise
        os.makedirs(intermediate_path, exist_ok=True)

    def run_deduplication_core(self, source_path: str, intermediate_path: str, allowed_extensions: Set[str],
                               progress_callback: Callable,
                               is_cancelled_callback: Callable[[], bool] = lambda: False) -> Tuple[
        str, List[DeduplicationResult]]:
        """
        v4.3 重构: 执行“扁平化、去重、重命名”的数据摄取核心流程。
        """
        task_run = self.db_handler.create_task_run(task_type='deduplication')
        files_to_scan = list(file_handler.scan_files(source_path, allowed_extensions))
        total_files = len(files_to_scan)
        processed_hashes, new_docs_to_save, deduplication_results, skipped_files = {}, [], [], []

        for i, file_path in enumerate(files_to_scan):
            try:
                if is_cancelled_callback():
                    logging.info("去重任务被用户取消。")
                    return "任务已取消", []

                progress_callback(i + 1, total_files, f"扫描文件: {os.path.basename(file_path)}")

                # 第一步：基于内容摘要去重
                content_slice = file_handler.get_content_slice(file_path)
                if not content_slice:
                    logging.warning(f"无法为文件 {file_path} 生成内容摘要，已跳过。")
                    continue

                content_hash = file_handler.calculate_content_hash(content_slice)

                if content_hash and content_hash not in processed_hashes:
                    processed_hashes[content_hash] = file_path

                    # 第二步：扁平化复制与冲突重命名
                    base_filename = os.path.basename(file_path)
                    destination_path = os.path.join(intermediate_path, base_filename)
                    unique_destination_path = _get_unique_filepath(destination_path)
                    unique_destination_path_normalized = unique_destination_path.replace('\\', '/')

                    shutil.copy2(file_path, unique_destination_path)

                    logging.debug(
                        f"[DIAGNOSTIC|orchestrator.dedup] Saving to DB with authoritative path: {unique_destination_path_normalized}")
                    new_docs_to_save.append(Document(
                        file_hash=content_hash,
                        file_path=unique_destination_path_normalized,
                        content_slice=content_slice
                    ))
                elif content_hash:
                    deduplication_results.append(
                        DeduplicationResult(task_run_id=task_run.id, duplicate_file_path=file_path,
                                            original_file_hash=content_hash))

            except Exception as e:
                logging.error(f"处理文件 {file_path} 时发生严重错误，已跳过此文件。", exc_info=True)
                skipped_files.append(file_path)

        if new_docs_to_save: self.db_handler.bulk_insert_documents(new_docs_to_save)
        if deduplication_results: self.db_handler.bulk_insert_deduplication_results(deduplication_results)

        self._is_engine_primed = False
        summary = f"去重任务完成！共找到 {len(deduplication_results)} 个重复文件。"
        if skipped_files:
            summary += f" \\n\\n警告：有 {len(skipped_files)} 个文件因处理时发生错误而被跳过。请检查日志获取详细信息。"
        summary += " 仅显示前100条，完整结果已存入数据库。" if len(deduplication_results) > 100 else " 详情已存入数据库。"
        self.db_handler.update_task_summary(task_run.id, summary)
        return summary, deduplication_results[:100]

    def run_vectorization(self, progress_callback: Callable,
                          is_cancelled_callback: Callable[[], bool] = lambda: False) -> str:
        """
        为数据库中尚未处理的文档计算并存储其特征向量。
        """
        docs_to_vectorize = self.db_handler.get_documents_without_vectors()
        if not docs_to_vectorize: return "所有文档均已向量化，无需操作。"

        content_slices = [(doc.content_slice or "") for doc in docs_to_vectorize]
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

    def prime_similarity_engine(self, force_reload: bool = False,
                                is_cancelled_callback: Callable[[], bool] = lambda: False) -> None:
        """
        v4.3.1 修复: 预热引擎，加载向量和元数据，并重新训练 TF-IDF 模型。
        """
        if self._is_engine_primed and not force_reload:
            return

        logging.info("正在预热相似度引擎...")
        all_docs = self.db_handler.get_all_documents()
        docs_with_vectors = [doc for doc in all_docs if doc.feature_vector]

        if not docs_with_vectors:
            self.similarity_engine.feature_matrix = None
            self.similarity_engine.doc_map = []
            self._is_engine_primed = True
            logging.info("引擎预热完成，但未找到任何已向量化的文档。")
            return

        # v4.3.1 修复: 重新训练 TF-IDF 模型以支持关键词提取
        logging.info("正在基于现有内容切片重新训练 TF-IDF 模型...")
        content_slices_for_fitting = [doc.content_slice for doc in docs_with_vectors if doc.content_slice]
        if content_slices_for_fitting:
            self.similarity_engine.vectorizer.fit(content_slices_for_fitting)
            logging.info(f"TF-IDF 模型已在 {len(content_slices_for_fitting)} 个文档上成功再训练。")
        else:
            logging.warning("未找到任何内容切片来训练 TF-IDF 模型，关键词提取功能将不可用。")

        vectors, doc_map = [], []
        for doc in docs_with_vectors:
            if is_cancelled_callback():
                logging.info("引擎预热被用户取消。")
                return
            try:
                vectors.append(_json_to_vector(doc.feature_vector))
                doc_map.append({'id': doc.id, 'file_path': doc.file_path})
            except (json.JSONDecodeError, KeyError) as e:
                logging.error(f"无法解析文件 '{doc.file_path}' 的特征向量JSON。将跳过此文件。错误: {e}")

        if vectors:
            self.similarity_engine.feature_matrix = vstack(vectors)
            self.similarity_engine.doc_map = doc_map
            logging.info(f"引擎预热成功，已加载 {len(doc_map)} 个文档的向量和映射。")
        else:
            self.similarity_engine.feature_matrix = None
            self.similarity_engine.doc_map = []
            logging.info("引擎预热完成，但未能成功加载任何向量。")

        self._is_engine_primed = True

    def find_top_n_similar_for_file(self, target_file_id: int, n: int,
                                    is_cancelled_callback: Callable[[], bool] = lambda: False) -> List[Dict[str, Any]]:
        """
        v4.3 修复: 为指定文件 ID 查找最相似的 N 个其他文件。
        """
        logging.info(f"收到为文件 ID {target_file_id} 查找 {n} 个相似文件的请求。")
        self.prime_similarity_engine(is_cancelled_callback=is_cancelled_callback)
        if is_cancelled_callback() or not self._is_engine_primed or self.similarity_engine.feature_matrix is None:
            return []

        target_doc = self.db_handler.get_document_by_id(target_file_id)
        if not target_doc:
            logging.error(f"严重错误：无法在数据库中找到 ID 为 {target_file_id} 的文档。")
            return []

        doc_map = self.similarity_engine.doc_map
        target_index = -1
        for i, doc in enumerate(doc_map):
            if doc['id'] == target_file_id:
                target_index = i
                break
        
        if target_index == -1:
            logging.error(f"严重错误：无法在引擎的文档映射中找到 ID 为 {target_file_id} 的记录。")
            return []

        target_vector = self.similarity_engine.feature_matrix[target_index]
        indices, scores = self.similarity_engine.find_top_n_similar(target_vector, n=n)

        return [
            {
                'id': doc_map[i]['id'],
                'path': doc_map[i]['file_path'],
                'score': score
            } for i, score in zip(indices, scores)
        ]

    def run_kmeans_clustering(self, target_dir: str, k: int, progress_callback: Callable,
                              is_cancelled_callback: Callable[[], bool] = lambda: False) -> str:
        """
        在指定目录上执行 K-Means 聚类。
        """
        native_target_dir = os.path.normpath(target_dir)
        logging.info(
            f"Orchestrator 收到对目录 '{target_dir}' 的 K-Means 聚类请求 (K={k})。已规范化为: '{native_target_dir}'")

        self.prime_similarity_engine(is_cancelled_callback=is_cancelled_callback)
        if is_cancelled_callback(): return "任务已取消"
        if self.similarity_engine.feature_matrix is None or self.similarity_engine.feature_matrix.shape[0] == 0:
            return "没有可供聚类的文档 (引擎预热失败，可能因上游向量化错误)。"

        try:
            task_run = self.db_handler.create_task_run(task_type='kmeans_clustering')
            success = self.cluster_engine.run_kmeans_clustering(native_target_dir, k, progress_callback,
                                                                is_cancelled_callback)
            if is_cancelled_callback():
                summary = "K-Means 聚类任务被用户取消。"
            elif success:
                summary = f"对目录 '{os.path.basename(native_target_dir)}' 的 K-Means 聚类已成功完成。"
            else:
                summary = f"K-Means 聚类操作已跳过，详情请查看日志。"
            self.db_handler.update_task_summary(task_run.id, summary)
            return summary
        except Exception as e:
            logging.error(f"在执行 K-Means 聚类时发生意外错误: {e}", exc_info=True)
            return f"K-Means 聚类失败: {e}"

    def run_similarity_clustering(self, target_dir: str, threshold: float, progress_callback: Callable,
                                  is_cancelled_callback: Callable[[], bool] = lambda: False) -> str:
        """
        在指定目录上执行相似度分组。
        """
        native_target_dir = os.path.normpath(target_dir)
        logging.info(
            f"Orchestrator 收到对目录 '{target_dir}' 的相似度分组请求 (阈值={threshold})。已规范化为: '{native_target_dir}'")

        self.prime_similarity_engine(is_cancelled_callback=is_cancelled_callback)
        if is_cancelled_callback(): return "任务已取消"
        if self.similarity_engine.feature_matrix is None or self.similarity_engine.feature_matrix.shape[0] == 0:
            return "没有可供聚类的文档 (引擎预热失败，可能因上游向量化错误)。"

        try:
            task_run = self.db_handler.create_task_run(task_type='similarity_clustering')
            success = self.cluster_engine.run_similarity_clustering(native_target_dir, threshold, progress_callback,
                                                                    is_cancelled_callback)
            if is_cancelled_callback():
                summary = "相似度分组任务被用户取消。"
            elif success:
                summary = f"对目录 '{os.path.basename(native_target_dir)}' 的相似度分组已成功完成。"
            else:
                summary = f"相似度分组操作已跳过，详情请查看日志。"
            self.db_handler.update_task_summary(task_run.id, summary)
            return summary
        except Exception as e:
            logging.error(f"在执行相似度分组时发生意外错误: {e}", exc_info=True)
            return f"相似度分组失败: {e}"

    def run_filename_search(self, keyword: str, intermediate_path: str, target_path: str, allowed_extensions: Set[str],
                            progress_callback: Callable, is_cancelled_callback: Callable[[], bool] = lambda: False) -> \
    Tuple[str, List[SearchResult]]:
        """在中间文件夹中按文件名搜索，并将结果存入数据库。"""
        task_run = self.db_handler.create_task_run(task_type='filename_search')
        files_to_scan = list(file_handler.scan_files(intermediate_path, allowed_extensions))
        if not files_to_scan: return "中间文件夹中没有可供搜索的文件。", []

        matched_files = [p for p in files_to_scan if keyword.lower() in os.path.basename(p).lower()]
        if not matched_files: return f"没有找到文件名包含 '{keyword}' 的文件。", []

        search_results = [SearchResult(task_run_id=task_run.id, keyword=keyword, matched_file_path=p) for p in
                          matched_files]
        self.db_handler.bulk_insert_search_results(search_results)

        destination_dir = os.path.join(target_path, f"文件名包含_{keyword}")
        os.makedirs(destination_dir, exist_ok=True)
        skipped_files = []
        for i, file_path in enumerate(matched_files):
            if is_cancelled_callback():
                logging.info("文件名搜索任务被用户取消。")
                return "任务已取消", []
            progress_callback(i + 1, len(matched_files), f"正在复制: {os.path.basename(file_path)}")
            try:
                shutil.copy2(file_path, destination_dir)
            except PermissionError:
                logging.warning(f"权限错误：无法将搜索到的文件 {file_path} 复制到目标目录，可能文件已被锁定。将跳过复制。")
                skipped_files.append(file_path)

        summary = f"文件名搜索完成！共找到并复制了 {len(matched_files)} 个文件。"
        if skipped_files:
            summary += f" \\n\\n警告：有 {len(skipped_files)} 个文件因权限问题被跳过（可能已被其他程序锁定）。"
        summary += " 仅显示前100条，完整结果已存入数据库。" if len(matched_files) > 100 else " 详情已存入数据库。"
        self.db_handler.update_task_summary(task_run.id, summary)
        return summary, search_results[:100]

    def run_content_search(self, keyword: str, target_path: str, progress_callback: Callable,
                           is_cancelled_callback: Callable[[], bool] = lambda: False) -> Tuple[str, List[SearchResult]]:
        """
        在所有文档的预存内容切片中搜索关键词。
        """
        task_run = self.db_handler.create_task_run(task_type='content_search')
        all_docs = self.db_handler.get_all_documents()
        if not all_docs: return "数据库中没有可供搜索的文档记录。", []

        matched_paths = []
        for i, doc in enumerate(all_docs):
            if is_cancelled_callback():
                logging.info("内容搜索任务被用户取消。")
                return "任务已取消", []
            progress_callback(i + 1, len(all_docs), f"正在扫描: {os.path.basename(doc.file_path)}")

            content_slice = doc.content_slice or ""  # 确保 content_slice 不为 None
            if keyword.lower() in content_slice.lower():
                matched_paths.append(doc.file_path)

        if not matched_paths: return f"没有找到内容包含 '{keyword}' 的文件。", []

        search_results = [SearchResult(task_run_id=task_run.id, keyword=keyword, matched_file_path=p) for p in
                          matched_paths]
        self.db_handler.bulk_insert_search_results(search_results)

        destination_dir = os.path.join(target_path, f"内容包含_{keyword}")
        os.makedirs(destination_dir, exist_ok=True)
        skipped_files = []
        for i, file_path in enumerate(matched_paths):
            if is_cancelled_callback():
                logging.info("内容搜索任务被用户取消。")
                return "任务已取消", []
            progress_callback(i + 1, len(matched_paths), f"正在复制: {os.path.basename(file_path)}")
            try:
                shutil.copy2(file_path, destination_dir)
            except PermissionError:
                logging.warning(f"权限错误：无法将搜索到的文件 {file_path} 复制到目标目录，可能文件已被锁定。将跳过复制。")
                skipped_files.append(file_path)

        summary = f"文件内容搜索完成！共找到并复制了 {len(matched_paths)} 个文件。"
        if skipped_files:
            summary += f" \\n\\n警告：有 {len(skipped_files)} 个文件因权限问题被跳过（可能已被其他程序锁定）。"
        summary += " 仅显示前100条，完整结果已存入数据库。" if len(matched_files) > 100 else " 详情已存入数据库。"
        self.db_handler.update_task_summary(task_run.id, summary)
        return summary, search_results[:100]
