# -*- coding: utf-8 -*-
"""
交互式分析与搜索服务模块 (v2.9 - 深度限制修复)。

此版本为目录树生成功能增加了深度限制，以防止 UI 在渲染
超大目录树时因堆栈溢出而崩溃。
"""

import logging
import os
import shutil
from typing import List, Dict, Any, Callable

from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Document
from qzen_core.similarity_engine import SimilarityEngine

# 定义一个无操作的回调函数作为默认值
def _noop_callback(*args, **kwargs):
    pass

class AnalysisService:
    """
    封装了所有用于分析和搜索的后端逻辑。
    """

    def __init__(self, db_handler: DatabaseHandler, sim_engine: SimilarityEngine):
        """
        初始化分析服务。
        """
        self.db_handler = db_handler
        self.sim_engine = sim_engine

    def populate_directory_tree(self, root_path: str, tree_data: Dict[str, Any], max_depth: int | None = None, progress_callback: Callable = _noop_callback, is_cancelled_callback: Callable[[], bool] = lambda: False) -> None:
        """
        从数据库读取文件路径，并填充一个预先存在的字典来代表目录树。
        v2.9 修正: 增加 max_depth 参数以限制构建的目录深度。
        """
        logging.info(f"正在从数据库为路径 '{root_path}' 构建目录树 (最大深度: {max_depth})...")
        docs = self.db_handler.get_all_documents()
        
        norm_root_path = os.path.normpath(root_path)
        tree_data.clear()
        tree_data.update({"name": os.path.basename(norm_root_path), "type": "directory", "children": []})
        
        if not docs:
            logging.info("目录树构建完成 (无文档)。")
            return

        node_map = {".": tree_data}

        total_docs = len(docs)
        for i, doc in enumerate(docs):
            if is_cancelled_callback(): raise InterruptedError("任务已取消")
            progress_callback(i + 1, total_docs, f"正在构建目录树: {os.path.basename(doc.file_path)}")

            try:
                relative_path = os.path.relpath(doc.file_path, norm_root_path)
            except ValueError:
                logging.warning(f"文件路径 '{doc.file_path}' 不在根目录 '{norm_root_path}' 下，跳过。")
                continue

            parts = relative_path.split(os.sep)
            
            # v2.9 深度限制检查
            if max_depth is not None and len(parts) > max_depth:
                continue

            current_path_key = "."
            for part in parts[:-1]:
                parent_node = node_map[current_path_key]
                current_path_key = os.path.join(current_path_key, part)
                child_node = next((child for child in parent_node["children"] if child["name"] == part), None)
                if not child_node:
                    child_node = {"name": part, "type": "directory", "children": []}
                    parent_node["children"].append(child_node)
                node_map[current_path_key] = child_node
            
            # 只有当父目录的深度在允许范围内时，才添加文件节点
            if max_depth is None or len(parts) <= max_depth:
                file_node = {"name": parts[-1], "type": "file", "file_id": doc.id}
                node_map[current_path_key]["children"].append(file_node)

        logging.info("目录树构建完成。")

    def find_similar_to_file(self, file_id: int, top_n: int = 10, progress_callback: Callable = _noop_callback, is_cancelled_callback: Callable[[], bool] = lambda: False) -> List[Document]:
        logging.info(f"收到为文件 ID {file_id} 查找 {top_n} 个相似文件的请求。")
        
        if self.sim_engine.feature_matrix is None or not self.sim_engine.doc_map:
            logging.warning("相似度引擎尚未预热，无法查找相似文件。")
            return []

        doc_map = self.sim_engine.doc_map
        
        try:
            target_index = next(i for i, doc in enumerate(doc_map) if doc['id'] == file_id)
        except StopIteration:
            logging.warning(f"无法在预热的文档映射中找到文件 ID: {file_id}。")
            return []
        
        target_vector = self.sim_engine.feature_matrix[target_index]
        
        if is_cancelled_callback():
            logging.info("查找相似文件任务被取消。")
            return []
            
        progress_callback(1, 3, "正在计算相似度...")
        indices, _ = self.sim_engine.find_top_n_similar(target_vector, n=top_n)
        
        if not indices:
            return []
            
        progress_callback(2, 3, "正在检索文档信息...")
        similar_doc_ids = [doc_map[i]['id'] for i in indices]
        
        if is_cancelled_callback():
            return []
            
        similar_docs = self.db_handler.get_documents_by_ids(similar_doc_ids)
        
        doc_id_map = {doc.id: doc for doc in similar_docs}
        sorted_results = [doc_id_map[doc_id] for doc_id in similar_doc_ids if doc_id in doc_id_map]
        
        progress_callback(3, 3, "完成。")
        logging.info(f"为文件 ID {file_id} 成功找到 {len(sorted_results)} 个相似文件。")
        
        return sorted_results

    def search_by_filename(self, keyword: str, progress_callback: Callable = _noop_callback, is_cancelled_callback: Callable[[], bool] = lambda: False) -> List[Document]:
        return self.db_handler.search_documents_by_filename(keyword)

    def search_by_content(self, keyword: str, progress_callback: Callable = _noop_callback, is_cancelled_callback: Callable[[], bool] = lambda: False) -> List[Document]:
        return self.db_handler.search_documents_by_content(keyword)

    def export_search_results(self, doc_ids: List[int], keyword: str, export_base_dir: str, progress_callback: Callable = _noop_callback, is_cancelled_callback: Callable[[], bool] = lambda: False) -> str:
        if not doc_ids: return ""
        
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '_')).rstrip() or "导出结果"
        export_dir = os.path.normpath(os.path.join(export_base_dir, safe_keyword))
        os.makedirs(export_dir, exist_ok=True)

        docs_to_export = self.db_handler.get_documents_by_ids(doc_ids)
        total_docs = len(docs_to_export)
        for i, doc in enumerate(docs_to_export):
            if is_cancelled_callback(): raise InterruptedError("任务已取消")
            progress_callback(i + 1, total_docs, f"正在导出: {os.path.basename(doc.file_path)}")
            try:
                shutil.copy2(doc.file_path, os.path.join(export_dir, os.path.basename(doc.file_path)))
            except Exception as e:
                logging.error(f"无法复制文件 {doc.file_path} 到 {export_dir}: {e}")

        return export_dir
