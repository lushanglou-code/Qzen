# -*- coding: utf-8 -*-
"""
数据摄取服务模块 (v4.2.2 - 修复 TypeError)。

此版本根据 `architecture.rst` v3.5 的设计，对去重逻辑进行了根本性重构。
系统现在基于“三段式内容切片”的哈希值 (`slice_hash`) 进行去重，取代了
原有的完整文件哈希 (`file_hash`) 方案。

此版本紧急修复了在调用 `file_handler.get_content_slice` 时由于残留的
旧代码而导致的 `TypeError`，确保所有函数调用都与 v4.2.1 的接口定义
保持一致。
"""

import logging
import os
import json
import shutil
from typing import List, Set, Callable, Dict, Tuple

from scipy.sparse import csr_matrix

from qzen_data.database_handler import DatabaseHandler
from qzen_data import file_handler
from qzen_data.models import Document
from qzen_core.similarity_engine import SimilarityEngine


# 定义一个无操作的回调函数作为默认值
def _noop_callback(*args, **kwargs):
    pass


def _vector_to_json(vector: csr_matrix) -> str:
    """将稀疏矩阵 (CSR Matrix) 序列化为 JSON 字符串。"""
    return json.dumps({
        'data': vector.data.tolist(),
        'indices': vector.indices.tolist(),
        'indptr': vector.indptr.tolist(),
        'shape': vector.shape
    })


class IngestionService:
    """
    编排数据摄取、去重、预处理和数据库构建的整个流程。
    """

    def __init__(self, db_handler: DatabaseHandler):
        """
        初始化 IngestionService。
        """
        self.db_handler = db_handler
        self.allowed_extensions = {
            '.txt', '.md', '.pdf', '.docx', '.pptx', '.xlsx', '.xls'
        }

    def _find_unique_filepath(self, file_path: str) -> str:
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

    def execute(self, source_dir: str, intermediate_dir: str, custom_stopwords: List[str] = None,
                progress_callback: Callable = _noop_callback,
                is_cancelled_callback: Callable[[], bool] = lambda: False) -> bool:
        """
        执行完整的数据摄取工作流，并支持进度报告和取消操作。
        """
        logging.info("--- 开始执行数据摄取工作流 (v4.2.2) ---")
        try:
            # 步骤 1: 清理并准备工作区
            progress_callback(0, 100, "正在准备工作空间...")
            self.db_handler.recreate_tables()
            if os.path.exists(intermediate_dir):
                shutil.rmtree(intermediate_dir)
            os.makedirs(intermediate_dir)
            if is_cancelled_callback(): return False

            # 步骤 2: 基于内容摘要去重并复制文件
            unique_files_map = self._deduplicate_and_copy(source_dir, intermediate_dir, progress_callback,
                                                          is_cancelled_callback)
            if is_cancelled_callback(): return False

            # 步骤 3: 构建数据库记录并处理文件名冲突
            progress_callback(90, 100, "正在构建数据库并处理文件名冲突...")
            self._build_database_records_and_resolve_conflicts(unique_files_map)
            if is_cancelled_callback(): return False

            # 步骤 4: 向量化
            self._process_content_and_vectorize(custom_stopwords, progress_callback, is_cancelled_callback)
            if is_cancelled_callback(): return False

            logging.info("--- 数据摄取工作流成功完成 ---")
            progress_callback(100, 100, "全部完成！")
            return True

        except Exception as e:
            logging.error(f"数据摄取工作流执行失败: {e}", exc_info=True)
            return False

    def _deduplicate_and_copy(self, source_dir: str, intermediate_dir: str, progress_callback: Callable,
                              is_cancelled_callback: Callable[[], bool]) -> Dict[str, Tuple[str, str]]:
        """
        v4.2.2: 扫描文件，基于内容摘要 (slice) 去重，并复制文件。

        Returns:
            一个字典，键是内容摘要的哈希 (slice_hash)，值是一个元组，
            包含文件在中间目录的路径和内容摘要本身。
            {slice_hash: (dest_path, content_slice)}
        """
        logging.info(f"开始扫描源文件夹并基于内容摘要去重: {source_dir}")
        files_to_scan = list(file_handler.scan_files(source_dir, self.allowed_extensions))
        total_files = len(files_to_scan)
        unique_slice_hashes: Set[str] = set()
        unique_files_map: Dict[str, Tuple[str, str]] = {}

        for i, filepath in enumerate(files_to_scan):
            if is_cancelled_callback():
                logging.info("数据摄取任务在去重阶段被取消。")
                raise InterruptedError("任务已取消")

            base_filename = os.path.basename(filepath)
            progress_callback(i + 1, total_files, f"正在分析与去重: {base_filename}")

            content_slice = file_handler.get_content_slice(filepath)
            if not content_slice:
                logging.warning(f"无法为文件生成内容摘要，已跳过: {filepath}")
                continue

            slice_hash = file_handler.calculate_content_hash(content_slice)

            if slice_hash not in unique_slice_hashes:
                unique_slice_hashes.add(slice_hash)

                relative_path = os.path.relpath(filepath, source_dir)
                dest_path = os.path.normpath(os.path.join(intermediate_dir, relative_path))

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(filepath, dest_path)
                unique_files_map[slice_hash] = (dest_path, content_slice)

        logging.info(f"扫描完成。共处理 {len(files_to_scan)} 个文件，发现 {len(unique_slice_hashes)} 个唯一内容摘要。")
        return unique_files_map

    def _build_database_records_and_resolve_conflicts(self, files_map: Dict[str, Tuple[str, str]]) -> None:
        """
        v4.2.2: 在数据库中创建记录，并检测和解决文件名冲突。
        """
        logging.info("开始在数据库中构建文档记录...")
        if not files_map:
            logging.info("没有唯一文件可用于构建数据库记录。")
            return

        documents_to_insert = [
            Document(
                file_hash=slice_hash,  # v3.5: 存储内容摘要的哈希
                file_path=path_and_slice[0],
                content_slice=path_and_slice[1],  # v3.5: 直接存入内容摘要
                feature_vector=""
            ) for slice_hash, path_and_slice in files_map.items()
        ]

        inserted_docs = self.db_handler.bulk_insert_documents(documents_to_insert)
        if not inserted_docs:
            logging.warning("批量插入后没有返回任何文档记录，无法进行文件名冲突检查。")
            return

        logging.info("开始检测并解决文件名冲突...")
        basename_map = {}
        for doc in inserted_docs:
            basename = os.path.basename(doc.file_path)
            basename_map.setdefault(basename, []).append(doc)

        docs_to_update_in_db = []
        rename_count = 0
        for basename, docs_with_same_name in basename_map.items():
            if len(docs_with_same_name) > 1:
                logging.warning(f"发现文件名冲突: '{basename}' 被 {len(docs_with_same_name)} 个不同内容的文件使用。")
                for doc_to_rename in docs_with_same_name[1:]:
                    original_path = doc_to_rename.file_path
                    try:
                        new_path = self._find_unique_filepath(original_path)
                        os.rename(original_path, new_path)
                        doc_to_rename.file_path = new_path
                        docs_to_update_in_db.append(doc_to_rename)
                        rename_count += 1
                        logging.info(
                            f"  - 已重命名: '{os.path.basename(original_path)}' -> '{os.path.basename(new_path)}'")
                    except OSError as e:
                        logging.error(f"重命名文件 '{original_path}' 失败: {e}", exc_info=True)

        if docs_to_update_in_db:
            logging.info(f"共重命名了 {rename_count} 个文件，现在将变更更新到数据库...")
            self.db_handler.bulk_update_documents(docs_to_update_in_db)
        else:
            logging.info("在本次任务中未发现文件名冲突。")

    def _process_content_and_vectorize(self, custom_stopwords: List[str], progress_callback: Callable,
                                       is_cancelled_callback: Callable[[], bool]) -> None:
        """
        v4.2.2: 直接从数据库记录中获取内容摘要，计算向量并更新数据库。
        """
        logging.info("开始为新文档进行向量化 (v4.2.2 优化流程)...")
        docs_to_process = self.db_handler.get_all_documents()
        if not docs_to_process:
            logging.info("数据库中没有需要处理的文档。")
            return

        valid_docs = [doc for doc in docs_to_process if doc.content_slice and not doc.feature_vector]
        if not valid_docs:
            logging.info("所有文档均已向量化，或没有可供处理的内容摘要。")
            return

        total_docs = len(valid_docs)
        logging.info(f"共找到 {total_docs} 个需要向量化的文档。")

        content_slices = [doc.content_slice for doc in valid_docs]

        logging.info("开始使用 SimilarityEngine 进行批量向量化...")
        sim_engine = SimilarityEngine(custom_stopwords=custom_stopwords)
        feature_matrix = sim_engine.vectorize_documents(content_slices)

        for i, doc in enumerate(valid_docs):
            if is_cancelled_callback(): raise InterruptedError("任务已取消")
            progress_callback(i + 1, total_docs, f"正在向量化: {os.path.basename(doc.file_path)}")
            vector = feature_matrix[i]
            doc.feature_vector = _vector_to_json(vector)

        logging.info("开始将特征向量批量更新到数据库...")
        self.db_handler.bulk_update_documents(valid_docs)