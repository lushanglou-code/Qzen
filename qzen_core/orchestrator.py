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
from qzen_data.models import Document
from qzen_core.similarity_engine import SimilarityEngine
from qzen_core.cluster_engine import ClusterEngine, find_longest_common_prefix


def _vector_to_json(vector: csr_matrix) -> str:
    """
    将稀疏矩阵 (CSR Matrix) 序列化为 JSON 字符串。

    为了能将 scikit-learn 计算出的特征向量存入数据库，需要将其转换为可存储的格式。
    JSON 是一个通用的选择。

    Args:
        vector: 来自 scikit-learn 的 CSR 格式稀疏矩阵。

    Returns:
        包含矩阵数据的 JSON 字符串。
    """
    return json.dumps({
        'data': vector.data.tolist(),
        'indices': vector.indices.tolist(),
        'indptr': vector.indptr.tolist(),
        'shape': vector.shape
    })


def _json_to_vector(json_str: str) -> csr_matrix:
    """
    将 JSON 字符串反序列化为稀疏矩阵 (CSR Matrix)。

    从数据库读取特征向量字符串后，需要此函数将其还原为 scikit-learn
    可以使用的稀疏矩阵对象。

    Args:
        json_str: 包含稀疏矩阵数据的 JSON 字符串。

    Returns:
        一个 CSR 格式的稀疏矩阵。
    """
    data = json.loads(json_str)
    return csr_matrix((data['data'], data['indices'], data['indptr']), shape=data['shape'])


class Orchestrator:
    """
    协调各个模块以完成复杂的业务流程。

    Orchestrator 是业务逻辑层的核心，它封装了所有主要的用户功能，
    如去重、向量化、聚类等。它通过组合 `qzen_data` 和 `qzen_core`
    中的低层模块来响应来自 UI 层的用户请求。

    Attributes:
        db_handler (database_handler.DatabaseHandler): 数据库操作的句柄。
        similarity_engine (SimilarityEngine): 用于计算和比较文档相似度的引擎。
        cluster_engine (ClusterEngine): 用于根据相似度对文档进行聚类的引擎。
    """
    def __init__(self, db_handler: database_handler.DatabaseHandler):
        """
        初始化 Orchestrator。

        Args:
            db_handler: 一个已经实例化的 `DatabaseHandler` 对象，用于数据库交互。
        """
        self.db_handler = db_handler
        self.similarity_engine = SimilarityEngine()
        self.cluster_engine = ClusterEngine()
        self._is_engine_primed: bool = False  # 标记相似度引擎是否已加载数据
        self._doc_path_map: List[str] = []  # 缓存文档路径，其索引与引擎中特征矩阵的行索引一致

    def prepare_deduplication_workspace(self, intermediate_path: str) -> None:
        """
        为全新的去重任务准备工作空间。

        此操作具有破坏性，它会：
        1. 清空并重建数据库中的所有表格。
        2. 删除并重建用于存放唯一文件的中间文件夹。

        此方法应在主 UI 线程中执行，因为它涉及文件系统和数据库的准备工作，
        需要在后台任务开始前完成。

        Args:
            intermediate_path: 中间文件夹的路径。

        Raises:
            OSError: 如果删除或创建中间文件夹时发生文件系统错误。
        """
        logging.info("--- 准备全新的去重任务工作空间 ---")
        logging.info("正在清空并重建数据库表...")
        self.db_handler.recreate_tables()
        logging.info("数据库表已清空并重建。")

        logging.info(f"正在清空中间文件夹: {intermediate_path}...")
        if os.path.exists(intermediate_path):
            try:
                shutil.rmtree(intermediate_path)
                logging.info(f"已删除旧的中间文件夹: {intermediate_path}")
            except OSError as e:
                logging.error(f"无法删除中间文件夹: {e}")
                raise
        os.makedirs(intermediate_path, exist_ok=True)
        logging.info(f"已创建新的中间文件夹: {intermediate_path}")

    def run_deduplication_core(self, source_path: str, intermediate_path: str, allowed_extensions: Set[str], progress_callback: Callable[[int, int, str], None]) -> List[str]:
        """
        执行核心的去重逻辑。

        扫描源文件夹中的所有文件，计算每个文件的哈希值。对于唯一的文
        件，将其复制到中间文件夹，并将其元信息存入数据库。

        此方法设计为在后台线程中运行。

        Args:
            source_path: 包含原始文档的源文件夹路径。
            intermediate_path: 用于存放唯一文档副本的中间文件夹路径。
            allowed_extensions: 一个包含允许处理的文件扩展名的集合 (例如, {'.txt', '.pdf'})。
            progress_callback: 一个回调函数，用于向 UI 线程报告进度。
                               它接受三个参数: (当前进度, 总量, 状态文本)。

        Returns:
            一个列表，包含所有因内容重复而未被复制的文件的完整路径。
        """
        logging.info("--- 开始核心去重扫描与复制任务 ---")
        files_to_scan = list(file_handler.scan_files(source_path, allowed_extensions))
        total_files = len(files_to_scan)
        processed_hashes = set()
        new_docs_to_save = []
        duplicate_files = []  # 用于存储重复文件的路径

        for i, file_path in enumerate(files_to_scan):
            base_name = os.path.basename(file_path)
            progress_callback(i + 1, total_files, f"扫描文件: {base_name}")
            file_hash = file_handler.calculate_file_hash(file_path)

            if file_hash and file_hash not in processed_hashes:
                # 这是一个新文件，处理它
                processed_hashes.add(file_hash)
                # 维持原始的目录结构
                destination_path = os.path.normpath(os.path.join(intermediate_path, os.path.relpath(file_path, source_path)))
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                shutil.copy2(file_path, destination_path)
                new_doc = Document(file_hash=file_hash, file_path=destination_path, feature_vector=None)
                new_docs_to_save.append(new_doc)
            elif file_hash:
                # 文件内容重复，记录其路径
                duplicate_files.append(file_path)

        if new_docs_to_save:
            logging.info(f"向数据库中批量插入 {len(new_docs_to_save)} 个新文档记录。")
            self.db_handler.bulk_insert_documents(new_docs_to_save)
        
        self._is_engine_primed = False  # 数据已更新，引擎需要重新预热
        progress_callback(total_files, total_files, "去重任务完成！")
        logging.info(f"--- 核心去重任务结束 --- 共找到 {len(duplicate_files)} 个重复文件。")
        return duplicate_files

    def run_vectorization(self, progress_callback: Callable[[int, int, str], None]) -> str:
        """
        为数据库中尚未处理的文档计算并存储其特征向量。

        该过程包括：
        1. 从数据库获取所有没有特征向量的文档。
        2. 为每个文档提取内容切片。
        3. 使用 TF-IDF 算法将所有内容切片批量转换为数值型特征向量。
        4. 将计算出的向量序列化后存回数据库。

        这是一个计算密集型操作，必须在后台线程中执行。

        Args:
            progress_callback: 用于报告进度的回调函数。

        Returns:
            一个描述操作结果的摘要字符串。
        """
        logging.info("开始文档向量化流程。")
        docs_to_vectorize = self.db_handler.get_documents_without_vectors()
        total_docs = len(docs_to_vectorize)
        if not docs_to_vectorize:
            progress_callback(1, 1, "所有文档均已向量化，无需操作。")
            return "所有文档均已向量化，无需操作。"

        # 提取所有需要处理的文档的内容摘要
        content_slices = [file_handler.get_content_slice(doc.file_path) for doc in docs_to_vectorize]
        
        progress_callback(0, total_docs, "正在计算TF-IDF特征向量...")
        feature_matrix = self.similarity_engine.vectorize_documents(content_slices)
        
        # 将向量与文档对象关联
        for i, doc in enumerate(docs_to_vectorize):
            progress_callback(i + 1, total_docs, f"准备向量: {os.path.basename(doc.file_path)}")
            doc.feature_vector = _vector_to_json(feature_matrix[i])
            
        logging.info(f"正在向数据库中批量更新 {len(docs_to_vectorize)} 个文档的特征向量。")
        self.db_handler.bulk_update_documents(docs_to_vectorize)
        
        self._is_engine_primed = False  # 特征已更新，引擎需要重新预热
        progress_callback(total_docs, total_docs, "向量化完成！")
        logging.info("文档向量化流程结束。")
        return f"向量化任务已成功完成，处理了 {total_docs} 个文档。"

    def prime_similarity_engine(self, force_reload: bool = False) -> None:
        """
        预热相似度引擎。

        该方法从数据库加载所有文档的特征向量，并将它们合并成一个大的
        稀疏矩阵，加载到 `SimilarityEngine` 中。同时，它会创建一个文档
        路径列表 `_doc_path_map`，其索引与特征矩阵的行索引严格对应。
        这使得后续可以根据矩阵行号快速查找到对应的文件路径。

        为了提高性能，引擎只有在被标记为“未预热”或被强制重新加载时
        才会真正执行加载操作。

        Args:
            force_reload: 如果为 True，则强制从数据库重新加载数据，即
                          使引擎已被标记为“已预热”。
        """
        if self._is_engine_primed and not force_reload:
            logging.info("相似度引擎已预热，跳过加载。")
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
                # 如果某个向量损坏，记录错误并跳过，以保证程序健壮性
                logging.error(f"无法解析文件 '{doc.file_path}' 的特征向量JSON。该向量可能已损坏或格式不兼容。将跳过此文件。错误: {e}")

        if not vectors:
            logging.error("没有成功加载任何有效的特征向量。")
            self.similarity_engine.feature_matrix = None
        else:
            # 使用 vstack 将所有独立的稀疏矩阵垂直堆叠成一个大矩阵
            self.similarity_engine.feature_matrix = vstack(vectors)
            
        self._doc_path_map = doc_paths
        self._is_engine_primed = True
        logging.info(f"相似度引擎预热完成，加载了 {len(self._doc_path_map)} 个向量。")

    def find_top_n_similar_for_file(self, target_file_path: str, n: int) -> List[Tuple[str, float]]:
        """
        为指定文件查找最相似的 N 个其他文件。

        Args:
            target_file_path: 目标文件的完整路径。
            n: 需要返回的相似文件数量。

        Returns:
            一个元组列表，每个元组包含 (相似文件的路径, 相似度得分)。
            如果找不到或发生错误，则返回空列表。
        """
        self.prime_similarity_engine() # 确保引擎已准备就绪
        if not self._is_engine_primed or self.similarity_engine.feature_matrix is None:
            return []
            
        try:
            # 根据文件路径找到它在特征矩阵中的行索引
            target_index = self._doc_path_map.index(os.path.normpath(target_file_path))
        except ValueError:
            logging.error(f"目标文件 '{target_file_path}' 不在已知的文档列表中。")
            return []
            
        target_vector = self.similarity_engine.feature_matrix[target_index]
        indices, scores = self.similarity_engine.find_top_n_similar(target_vector, n=n)
        
        # 将相似项的索引转换回文件路径
        return [(self._doc_path_map[i], score) for i, score in zip(indices, scores)]

    def run_clustering_and_renaming(self, target_path: str, similarity_threshold: float, progress_callback: Callable[[int, int, str], None]) -> List[Tuple[str, str]]:
        """
        对所有文档进行自动聚类和重命名。

        过程如下：
        1. 使用 `ClusterEngine` 对所有文档向量进行聚类。
        2. 对每个形成的簇：
           a. 找到簇内所有文件名的最长公共前缀作为新目录名。
              (如果前缀太短，则使用通用名称)
           b. 在目标路径下创建以此命名的子目录。
           c. 将簇内所有文件复制到该子目录，并按 "前缀_序号" 的格式重命名。

        Args:
            target_path: 存放整理结果的目标根目录。
            similarity_threshold: 用于聚类的相似度阈值 (0.0 到 1.0)。
            progress_callback: 用于报告进度的回调函数。

        Returns:
            一个元组列表，每个元组代表一个重命名操作，格式为
            (原始文件名, 新文件的完整路径)。
        """
        self.prime_similarity_engine()
        if self.similarity_engine.feature_matrix is None or self.similarity_engine.feature_matrix.shape[0] == 0:
            logging.warning("没有可供聚类的文档。")
            return []
            
        clusters = self.cluster_engine.cluster_documents(self.similarity_engine.feature_matrix, similarity_threshold)
        if not clusters:
            logging.info("在当前相似度阈值下，没有找到可以构成簇的相似文档。")
            return []
            
        os.makedirs(target_path, exist_ok=True)
        total_clusters = len(clusters)
        rename_map = []
        
        for i, cluster_indices in enumerate(clusters):
            progress_callback(i + 1, total_clusters, f"正在处理第 {i+1} 个文件簇...")
            original_paths = [self._doc_path_map[idx] for idx in cluster_indices]
            original_filenames = [os.path.basename(p) for p in original_paths]
            
            # 智能命名：尝试从文件名中找到共同点作为分类依据
            cluster_prefix = find_longest_common_prefix(original_filenames).strip()
            # 如果找不到有意义的公共前缀（例如太短），则使用一个通用的簇名称
            if len(cluster_prefix) < 3: 
                cluster_prefix = f"相似文件簇_{i+1}"
                
            cluster_dir = os.path.join(target_path, cluster_prefix)
            os.makedirs(cluster_dir, exist_ok=True)
            
            for j, original_path in enumerate(original_paths):
                _, extension = os.path.splitext(original_path)
                new_filename = f"{cluster_prefix}_{j+1}{extension}"
                destination_path = os.path.join(cluster_dir, new_filename)
                shutil.copy2(original_path, destination_path)
                rename_map.append((os.path.basename(original_path), destination_path))
                
        summary = f"聚类完成！共创建 {total_clusters} 个簇，重命名了 {len(rename_map)} 个文件。"
        logging.info(summary)
        return rename_map

    def run_filename_search(self, keyword: str, intermediate_path: str, target_path: str, allowed_extensions: Set[str], progress_callback: Callable[[int, int, str], None]) -> List[str]:
        """
        在中间文件夹中按文件名搜索，并将匹配的文件复制到目标文件夹。

        搜索是大小写不敏感的。匹配的文件会被复制到一个以搜索关键词
        命名的子目录中。

        Args:
            keyword: 用于搜索的关键词。
            intermediate_path: 被搜索的中间文件夹路径。
            target_path: 存放搜索结果的目标根目录。
            allowed_extensions: 一个文件扩展名集合，用于过滤扫描的文件。
            progress_callback: 用于报告进度的回调函数。

        Returns:
            一个列表，包含所有匹配到的文件的原始路径。
        """
        logging.info(f"开始按文件名搜索，关键词: '{keyword}'")
        files_to_scan = list(file_handler.scan_files(intermediate_path, allowed_extensions))
        if not files_to_scan: 
            logging.warning("中间文件夹中没有可供搜索的文件。")
            return []
            
        # 在文件名中进行大小写不敏感的包含性搜索
        matched_files = [p for p in files_to_scan if keyword.lower() in os.path.basename(p).lower()]
        
        if not matched_files: 
            logging.info(f"没有找到文件名包含 '{keyword}' 的文件。")
            return []
            
        destination_dir = os.path.join(target_path, f"文件名包含_{keyword}")
        os.makedirs(destination_dir, exist_ok=True)
        
        total_files = len(matched_files)
        for i, file_path in enumerate(matched_files):
            progress_callback(i + 1, total_files, f"正在复制: {os.path.basename(file_path)}")
            shutil.copy2(file_path, destination_dir)
            
        summary = f"文件名搜索完成！共找到并复制了 {total_files} 个文件。"
        logging.info(summary)
        return matched_files

    def run_content_search(self, keyword: str, target_path: str, progress_callback: Callable[[int, int, str], None]) -> List[str]:
        """
        在所有文档的内容切片中搜索关键词，并将匹配的文档复制到目标文件夹。

        搜索是大小写不敏感的。匹配的文档会被复制到一个以搜索关键词
        命名的子目录中。

        Args:
            keyword: 用于搜索的关键词。
            target_path: 存放搜索结果的目标根目录。
            progress_callback: 用于报告进度的回调函数。

        Returns:
            一个列表，包含所有内容切片匹配关键词的文档的原始路径。
        """
        logging.info(f"开始按文件内容搜索，关键词: '{keyword}'")
        all_docs = self.db_handler.get_all_documents()
        if not all_docs: 
            logging.warning("数据库中没有可供搜索的文档记录。")
            return []
            
        matched_paths = []
        total_docs = len(all_docs)
        for i, doc in enumerate(all_docs):
            progress_callback(i + 1, total_docs, f"正在扫描: {os.path.basename(doc.file_path)}")
            content_slice = file_handler.get_content_slice(doc.file_path)
            # 在内容切片中进行大小写不敏感的包含性搜索
            if keyword.lower() in content_slice.lower():
                matched_paths.append(doc.file_path)
                
        if not matched_paths: 
            logging.info(f"没有找到内容包含 '{keyword}' 的文件。")
            return []
            
        destination_dir = os.path.join(target_path, f"内容包含_{keyword}")
        os.makedirs(destination_dir, exist_ok=True)
        
        total_files = len(matched_paths)
        for i, file_path in enumerate(matched_paths):
            progress_callback(i + 1, total_files, f"正在复制: {os.path.basename(file_path)}")
            shutil.copy2(file_path, destination_dir)
            
        summary = f"文件内容搜索完成！共找到并复制了 {total_files} 个文件。"
        logging.info(summary)
        return matched_paths
