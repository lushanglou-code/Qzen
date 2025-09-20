# -*- coding: utf-8 -*-
"""
交互式分析与搜索服务模块 (v3.2 - 新增相似文件分析)。

此版本为相似文件查找返回了完整的结果（包括分数），并重构了
文件导出逻辑，以支持新功能。
"""

import logging
import os
import shutil
from typing import List, Dict, Any, Callable

from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Document
from qzen_core.orchestrator import Orchestrator # 引入 Orchestrator 以便进行类型提示

# 定义一个无操作的回调函数作为默认值
def _noop_callback(*args, **kwargs):
    pass

class AnalysisService:
    """
    封装了所有用于分析和搜索的后端逻辑。
    """

    def __init__(self, db_handler: DatabaseHandler, orchestrator: Orchestrator):
        """
        初始化分析服务。
        v3.2 修正: 直接注入 Orchestrator 以调用其方法。
        """
        self.db_handler = db_handler
        self.orchestrator = orchestrator

    def find_similar_to_file(self, file_id: int, top_n: int = 10, progress_callback: Callable = _noop_callback, is_cancelled_callback: Callable[[], bool] = lambda: False) -> List[Dict[str, Any]]:
        """
        查找与指定文件内容最相似的前 N 个其他文件。
        v3.2 修正: 直接调用 Orchestrator 的方法，并返回包含分数的完整结果。
        """
        logging.info(f"收到为文件 ID {file_id} 查找 {top_n} 个相似文件的请求。")
        
        # 确保引擎已预热
        self.orchestrator.prime_similarity_engine(is_cancelled_callback=is_cancelled_callback)
        if is_cancelled_callback(): return []

        # 直接调用并返回结果
        return self.orchestrator.find_top_n_similar_for_file(
            target_file_id=file_id, 
            n=top_n, 
            is_cancelled_callback=is_cancelled_callback
        )

    def export_files_by_ids(self, doc_ids: List[int], destination_dir: str, progress_callback: Callable = _noop_callback, is_cancelled_callback: Callable[[], bool] = lambda: False) -> str:
        """
        v3.2 新增: 一个通用的文件导出方法，根据文档 ID 列表将文件复制到指定目录。
        """
        if not doc_ids:
            logging.warning("导出请求被调用，但未提供任何文档 ID。")
            return ""
        
        os.makedirs(destination_dir, exist_ok=True)

        docs_to_export = self.db_handler.get_documents_by_ids(doc_ids)
        total_docs = len(docs_to_export)
        exported_count = 0

        for i, doc in enumerate(docs_to_export):
            if is_cancelled_callback():
                logging.info("文件导出任务被用户取消。")
                raise InterruptedError("任务已取消")
            
            progress_callback(i + 1, total_docs, f"正在导出: {os.path.basename(doc.file_path)}")
            try:
                shutil.copy2(doc.file_path, os.path.join(destination_dir, os.path.basename(doc.file_path)))
                exported_count += 1
            except Exception as e:
                logging.error(f"无法复制文件 {doc.file_path} 到 {destination_dir}: {e}")

        logging.info(f"文件导出完成，成功导出 {exported_count}/{total_docs} 个文件到目录: {destination_dir}")
        return destination_dir

    def export_search_results(self, doc_ids: List[int], keyword: str, export_base_dir: str, progress_callback: Callable = _noop_callback, is_cancelled_callback: Callable[[], bool] = lambda: False) -> str:
        """
        将指定的搜索结果文件复制到导出目录。
        v3.2 修正: 重构为调用通用的 export_files_by_ids 方法。
        """
        if not doc_ids:
            return ""
        
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '_')).rstrip() or "导出结果"
        export_dir = os.path.normpath(os.path.join(export_base_dir, f"关键词_{safe_keyword}"))
        
        return self.export_files_by_ids(doc_ids, export_dir, progress_callback, is_cancelled_callback)

    def search_by_filename(self, keyword: str, progress_callback: Callable = _noop_callback, is_cancelled_callback: Callable[[], bool] = lambda: False) -> List[Document]:
        return self.db_handler.search_documents_by_filename(keyword)

    def search_by_content(self, keyword: str, progress_callback: Callable = _noop_callback, is_cancelled_callback: Callable[[], bool] = lambda: False) -> List[Document]:
        return self.db_handler.search_documents_by_content(keyword)
