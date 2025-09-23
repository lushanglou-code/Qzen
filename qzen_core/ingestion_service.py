# -*- coding: utf-8 -*-
"""
数据摄取服务模块 (v3.4.1 - 实现文件名冲突重命名)。

此版本在 `_build_database_records` 方法中实现了完整的文件名冲突处理逻辑，
严格遵循 `architecture.rst` v3.4 的设计。在内容去重并插入数据库后，
服务会检查新入库的文件是否存在文件名相同但内容（哈希）不同的情况。

如果存在冲突，服务会自动对冲突文件进行重命名 (例如 `file.txt` -> `file (1).txt`)，
同步更新物理文件和数据库记录，从而完美解决了数据摄取阶段的全部去重需求。
"""

import logging
import os
import json
import shutil
from typing import List, Set, Callable

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
        logging.info("--- 开始执行数据摄取工作流 ---")
        try:
            # 步骤 1: 清理并准备工作区
            progress_callback(0, 100, "正在准备工作空间...")
            self.db_handler.recreate_tables()
            if os.path.exists(intermediate_dir):
                shutil.rmtree(intermediate_dir)
            os.makedirs(intermediate_dir)
            if is_cancelled_callback(): return False

            # 步骤 2: 基于内容去重并复制文件
            unique_files_map = self._deduplicate_and_copy(source_dir, intermediate_dir, progress_callback, is_cancelled_callback)
            if is_cancelled_callback(): return False

            # 步骤 3: 构建数据库记录并处理文件名冲突
            progress_callback(90, 100, "正在构建数据库并处理文件名冲突...")
            self._build_database_records_and_resolve_conflicts(unique_files_map)
            if is_cancelled_callback(): return False

            # 步骤 4: 内容提取与向量化
            self._process_content_and_vectorize(custom_stopwords, progress_callback, is_cancelled_callback)
            if is_cancelled_callback(): return False

            logging.info("--- 数据摄取工作流成功完成 ---")
            progress_callback(100, 100, "全部完成！")
            return True

        except Exception as e:
            logging.error(f"数据摄取工作流执行失败: {e}", exc_info=True)
            return False

    def _deduplicate_and_copy(self, source_dir: str, intermediate_dir: str, progress_callback: Callable, is_cancelled_callback: Callable[[], bool]) -> dict[str, str]:
        """扫描、基于内容去重并复制文件。"""
        logging.info(f"开始扫描源文件夹: {source_dir}")
        files_to_scan = list(file_handler.scan_files(source_dir, self.allowed_extensions))
        total_files = len(files_to_scan)
        unique_hashes: Set[str] = set()
        unique_files_map: dict[str, str] = {}

        for i, filepath in enumerate(files_to_scan):
            if is_cancelled_callback():
                logging.info("数据摄取任务在去重阶段被取消。")
                raise InterruptedError("任务已取消")
            progress_callback(i + 1, total_files, f"正在扫描与去重: {os.path.basename(filepath)}")

            file_hash = file_handler.calculate_file_hash(filepath)
            if file_hash and file_hash not in unique_hashes:
                unique_hashes.add(file_hash)
                
                relative_path = os.path.relpath(filepath, source_dir)
                dest_path = os.path.normpath(os.path.join(intermediate_dir, relative_path))
                
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                
                shutil.copy2(filepath, dest_path)
                unique_files_map[file_hash] = dest_path
        
        logging.info(f"扫描完成。共处理 {len(files_to_scan)} 个文件，发现 {len(unique_hashes)} 个唯一文件。")
        return unique_files_map

    def _build_database_records_and_resolve_conflicts(self, files_map: dict[str, str]) -> None:
        """
        在数据库中创建记录，并检测和解决文件名冲突。
        """
        logging.info("开始在数据库中构建文档记录...")
        if not files_map:
            logging.info("没有唯一文件可用于构建数据库记录。")
            return

        # 1. 准备要插入的 Document 对象
        documents_to_insert = [
            Document(
                file_hash=h, 
                file_path=p,
                content_slice="",
                feature_vector=""
            ) for h, p in files_map.items()
        ]
        
        # 2. 批量插入，并获取实际被插入的文档列表
        # 在当前流程中，因为是全新任务，这里会插入所有文档
        inserted_docs = self.db_handler.bulk_insert_documents(documents_to_insert)
        if not inserted_docs:
            logging.warning("批量插入后没有返回任何文档记录，无法进行文件名冲突检查。")
            return

        # 3. 检测并解决文件名冲突
        logging.info("开始检测并解决文件名冲突...")
        basename_map = {}
        for doc in inserted_docs:
            basename = os.path.basename(doc.file_path)
            basename_map.setdefault(basename, []).append(doc)

        docs_to_update_in_db = []
        rename_count = 0
        for basename, docs_with_same_name in basename_map.items():
            if len(docs_with_same_name) > 1:
                # 发现冲突：文件名相同，但内容（哈希）不同
                logging.warning(f"发现文件名冲突: '{basename}' 被 {len(docs_with_same_name)} 个不同内容的文件使用。")
                # 保留第一个，重命名其余的
                for doc_to_rename in docs_with_same_name[1:]:
                    original_path = doc_to_rename.file_path
                    try:
                        new_path = self._find_unique_filepath(original_path)
                        os.rename(original_path, new_path)
                        doc_to_rename.file_path = new_path
                        docs_to_update_in_db.append(doc_to_rename)
                        rename_count += 1
                        logging.info(f"  - 已重命名: '{os.path.basename(original_path)}' -> '{os.path.basename(new_path)}'")
                    except OSError as e:
                        logging.error(f"重命名文件 '{original_path}' 失败: {e}", exc_info=True)

        # 4. 如果有重命名发生，则批量更新数据库
        if docs_to_update_in_db:
            logging.info(f"共重命名了 {rename_count} 个文件，现在将变更更新到数据库...")
            self.db_handler.bulk_update_documents(docs_to_update_in_db)
        else:
            logging.info("在本次任务中未发现文件名冲突。")

    def _process_content_and_vectorize(self, custom_stopwords: List[str], progress_callback: Callable, is_cancelled_callback: Callable[[], bool]) -> None:
        """提取内容、计算向量并更新数据库，同时报告进度并检查取消。"""
        logging.info("开始为新文档提取内容并进行向量化...")
        docs_to_process = self.db_handler.get_all_documents()
        if not docs_to_process:
            return

        total_docs = len(docs_to_process)
        content_slices, valid_docs = [], []
        for i, doc in enumerate(docs_to_process):
            if is_cancelled_callback(): raise InterruptedError("任务已取消")
            progress_callback(i + 1, total_docs, f"提取内容: {os.path.basename(doc.file_path)}")
            content = file_handler.get_content_slice(doc.file_path)
            if content:
                doc.content_slice = content
                content_slices.append(content)
                valid_docs.append(doc)
        
        if not valid_docs: return

        logging.info("开始使用 SimilarityEngine 进行批量向量化...")
        sim_engine = SimilarityEngine(custom_stopwords=custom_stopwords)
        feature_matrix = sim_engine.vectorize_documents(content_slices)

        for i, doc in enumerate(valid_docs):
            if is_cancelled_callback(): raise InterruptedError("任务已取消")
            progress_callback(i + 1, len(valid_docs), f"正在向量化: {os.path.basename(doc.file_path)}")
            vector = feature_matrix[i]
            doc.feature_vector = _vector_to_json(vector)

        logging.info("开始将内容切片和特征向量批量更新到数据库...")
        self.db_handler.bulk_update_documents(valid_docs)
