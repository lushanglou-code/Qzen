# -*- coding: utf-8 -*-
"""
文件聚类引擎模块 (v4.0.11 - 诊断增强版)。

此版本为最终修复与诊断的整合版，旨在彻底解决文件扫描失败的回归错误，
并为整个扫描流程添加了详细的诊断日志。

核心逻辑:
1.  **恢复原生路径扫描 (来自 v4.0.8)**: 严格使用 os.path.normpath 和 os.path.join
    来构建与数据库记录一致的原生查询路径 (e.g., 'E:\\folder\\')，解决扫描为 0 的问题。
2.  **保留写时复制 (来自 v4.0.9)**: 通过 `copy.copy()` 创建浅拷贝来更新路径，
    解决内存状态污染导致的“文件未找到”和数据丢失问题。
3.  **增加诊断模式**: 如果主查询失败，会自动启动备用诊断模式，通过在内存中
    手动比对路径，来定位问题是出在数据库查询层面还是路径格式本身。

对于反复的错误和修复倒退，我深表歉意。
"""

import logging
import os
import json
import re
import shutil
import copy
from collections import defaultdict
from typing import List, Callable, Tuple

import numpy as np
from scipy.sparse import vstack, csr_matrix
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Document
from qzen_core.similarity_engine import SimilarityEngine

# --- 验证日志：如果此条出现在日志中，证明文件已成功更新 ---
logging.critical("ClusterEngine v4.0.11 已加载，诊断增强修复已应用。")
# ---------------------------------------------------------

# 定义一个无操作的回调函数作为默认值
def _noop_callback(*args, **kwargs):
    pass

def _json_to_vector(json_str: str) -> csr_matrix:
    """将 JSON 字符串反序列化为稀疏矩阵 (CSR Matrix)。"""
    data = json.loads(json_str)
    return csr_matrix((data['data'], data['indices'], data['indptr']), shape=data['shape'])


class ClusterEngine:
    """
    v4.0 架构: 封装了独立的 K-Means 和相似度聚类算法。
    """

    def __init__(self, db_handler: DatabaseHandler, sim_engine: SimilarityEngine):
        self.db_handler = db_handler
        self.sim_engine = sim_engine

    def run_kmeans_clustering(self, target_dir: str, k: int, 
                              progress_callback: Callable = _noop_callback, 
                              is_cancelled_callback: Callable[[], bool] = lambda: False) -> bool:
        """
        对指定目录(及其所有子目录)下的全部文件执行 K-Means 聚类。
        """
        logging.info(f"--- 开始对目录 '{target_dir}' 执行 K-Means 聚类 (K={k}) ---")
        try:
            all_docs = self._get_all_docs_recursively(target_dir)
            valid_docs = [doc for doc in all_docs if doc.feature_vector]
            if len(valid_docs) < k:
                logging.warning(
                    f"K-Means 操作已跳过：在扫描到的 {len(all_docs)} 个文件中，只有 {len(valid_docs)} 个文件拥有可用于聚类的特征向量。"
                    f"这通常是由于上游的文本提取或向量化步骤失败导致的。所需文件数：{k}。"
                )
                return False
            if is_cancelled_callback(): return False

            normalized_base_dir = os.path.normpath(target_dir)
            progress_callback(1, 3, "步骤 1/3: 正在执行 K-Means 算法...")
            move_plan, docs_to_update = self._calculate_kmeans_move_plan(valid_docs, normalized_base_dir, k)
            if is_cancelled_callback(): return False

            progress_callback(2, 3, "步骤 2/3: 正在移动文件...")
            self._execute_move_plan(move_plan, is_cancelled_callback)
            if is_cancelled_callback(): return False

            progress_callback(3, 3, "步骤 3/3: 正在更新数据库并清理目录...")
            if docs_to_update: self.db_handler.bulk_update_documents(docs_to_update)
            self._remove_empty_subdirectories(normalized_base_dir)

            logging.info(f"K-Means 聚类完成。共处理 {len(valid_docs)} 个文件，分为 {k} 个簇。")
            return True
        except Exception as e:
            logging.error(f"执行 K-Means 聚类时发生未知错误: {e}", exc_info=True)
            return False

    def run_similarity_clustering(self, target_dir: str, threshold: float, 
                                  progress_callback: Callable = _noop_callback, 
                                  is_cancelled_callback: Callable[[], bool] = lambda: False) -> bool:
        """
        对指定目录(及其所有子目录)下的全部文件执行相似度分组。
        """
        logging.info(f"--- 开始对目录 '{target_dir}' 执行相似度分组 (阈值={threshold}) ---")
        try:
            all_docs = self._get_all_docs_recursively(target_dir)
            valid_docs = [doc for doc in all_docs if doc.feature_vector]
            if len(valid_docs) <= 1:
                logging.warning(
                    f"相似度分组已跳过：在扫描到的 {len(all_docs)} 个文件中，只有 {len(valid_docs)} 个文件拥有可用于分组的特征向量。"
                    f"这通常是由于上游的文本提取或向量化步骤失败导致的。所需文件数：> 1。"
                )
                return False
            if is_cancelled_callback(): return False

            normalized_base_dir = os.path.normpath(target_dir)
            progress_callback(1, 3, "步骤 1/3: 正在计算文件相似度...")
            move_plan, docs_to_update = self._calculate_similarity_move_plan(valid_docs, normalized_base_dir, threshold)
            if not move_plan or is_cancelled_callback(): 
                logging.info("相似度分组已跳过：未找到任何相似度超过阈值的群组。")
                return False

            progress_callback(2, 3, "步骤 2/3: 正在移动文件...")
            self._execute_move_plan(move_plan, is_cancelled_callback)
            if is_cancelled_callback(): return False

            progress_callback(3, 3, "步骤 3/3: 正在更新数据库并清理目录...")
            if docs_to_update: self.db_handler.bulk_update_documents(docs_to_update)
            self._remove_empty_subdirectories(normalized_base_dir)

            logging.info(f"相似度分组完成。共找到 {len(docs_to_update)} 个文件被归入新簇。")
            return True
        except Exception as e:
            logging.error(f"执行相似度分组时发生未知错误: {e}", exc_info=True)
            return False

    def _get_all_docs_recursively(self, target_dir: str) -> List[Document]:
        """(扫描) 递归获取一个目录下所有文件的 Document 对象。"""
        with self.db_handler.get_session() as session:
            # --- v4.0.11 诊断日志 --- 
            logging.info(f"[诊断] 收到扫描目录请求: '{target_dir}'")
            native_dir = os.path.normpath(target_dir)
            logging.info(f"[诊断] 规范化为原生路径: '{native_dir}'")
            search_path = os.path.join(native_dir, '')
            logging.info(f"[诊断] 构建的最终查询路径: '{search_path}'")

            docs = session.query(Document).filter(Document.file_path.startswith(search_path)).all()
            logging.info(f"主查询完成，使用 startswith('{search_path}') 找到了 {len(docs)} 个匹配的文档。")

            if not docs:
                logging.warning("主查询未找到任何文档。启动备用诊断查询...")
                all_docs_in_db = session.query(Document).all()
                logging.warning(f"数据库中共有 {len(all_docs_in_db)} 条记录。现在逐一在内存中比对路径前缀...")
                
                manual_matches = [doc for doc in all_docs_in_db if doc.file_path and doc.file_path.startswith(search_path)]

                if manual_matches:
                    logging.error(f"[诊断结论] 严重错误：主查询失败，但备用诊断在内存中找到了 {len(manual_matches)} 个匹配项！这强烈暗示数据库驱动或 SQLAlchemy 的 startswith 方法存在 Bug。")
                    logging.error(f"[诊断] 匹配到的路径示例: {[d.file_path for d in manual_matches[:3]]}")
                    return manual_matches # 返回手动找到的文档，尝试让程序继续
                else:
                    logging.error("[诊断结论] 致命错误：主查询和备用诊断均未找到任何匹配项。这几乎可以肯定是传入的目录与数据库中的路径格式完全不符。")
                    db_paths_sample = [d.file_path for d in all_docs_in_db[:5]]
                    logging.error(f"[诊断] 用于查询的前缀: '{search_path}'")
                    logging.error(f"[诊断] 数据库中的路径示例: {db_paths_sample}")
            return docs

    def _calculate_kmeans_move_plan(self, docs: List[Document], base_dir: str, k: int) -> Tuple[List[Tuple[str, str]], List[Document]]:
        """(计算) 执行 K-Means 并返回移动计划和待更新的文档对象列表。"""
        feature_vectors = vstack([_json_to_vector(doc.feature_vector) for doc in docs])
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10).fit(feature_vectors)
        
        move_plan = []
        docs_to_update = []
        for doc, label in zip(docs, kmeans.labels_):
            original_path = doc.file_path
            new_dir = os.path.join(base_dir, str(label))
            new_path = os.path.join(new_dir, os.path.basename(original_path))
            
            move_plan.append((original_path, new_path))
            
            doc_for_update = copy.copy(doc)
            doc_for_update.file_path = new_path
            docs_to_update.append(doc_for_update)
            
        return move_plan, docs_to_update

    def _calculate_similarity_move_plan(self, docs: List[Document], base_dir: str, threshold: float) -> Tuple[List[Tuple[str, str]], List[Document]]:
        """(计算) 执行相似度分组并返回移动计划和待更新的文档对象列表。"""
        feature_vectors = vstack([_json_to_vector(doc.feature_vector) for doc in docs])
        sim_matrix = cosine_similarity(feature_vectors)
        
        num_docs = len(docs)
        clustered = [False] * num_docs
        move_plan = []
        docs_to_update = []

        for i in range(num_docs):
            if clustered[i]: continue
            similar_indices = [j for j in range(i + 1, num_docs) if not clustered[j] and sim_matrix[i, j] >= threshold]
            if not similar_indices: continue

            current_cluster_indices = [i] + similar_indices
            cluster_docs = [docs[idx] for idx in current_cluster_indices]
            for idx in current_cluster_indices: clustered[idx] = True

            cluster_content = [doc.content_slice for doc in cluster_docs]
            topic_name = self._extract_topic_keywords(cluster_content) or "相似文件簇"
            new_dir = os.path.join(base_dir, topic_name)

            for doc in cluster_docs:
                original_path = doc.file_path
                new_path = os.path.join(new_dir, os.path.basename(original_path))
                move_plan.append((original_path, new_path))
                
                doc_for_update = copy.copy(doc)
                doc_for_update.file_path = new_path
                docs_to_update.append(doc_for_update)

        return move_plan, docs_to_update

    def _execute_move_plan(self, move_plan: List[Tuple[str, str]], is_cancelled_callback: Callable[[], bool]) -> None:
        """(移动) 根据计划执行文件移动，并创建目标文件夹。"""
        for original_path, new_path in move_plan:
            if is_cancelled_callback(): return
            try:
                new_dir = os.path.dirname(new_path)
                if not os.path.exists(new_dir): os.makedirs(new_dir)
                
                native_original_path = os.path.normpath(original_path)
                native_new_path = os.path.normpath(new_path)
                if os.path.exists(native_original_path):
                    shutil.move(native_original_path, native_new_path)
                else:
                    logging.warning(f"文件在移动前未找到，可能已被前序操作移动。已跳过: {original_path}")
            except Exception as e:
                logging.error(f"移动文件 {original_path} 到 {new_path} 时失败: {e}")

    def _extract_topic_keywords(self, content_list: List[str], top_n: int = 3) -> str:
        """根据一组文本内容，提取能代表其主题的关键词。"""
        if not content_list: return ""
        try:
            tfidf_matrix = self.sim_engine.vectorizer.transform(content_list)
            summed_tfidf = np.array(tfidf_matrix.sum(axis=0)).flatten()
            feature_names = np.array(self.sim_engine.vectorizer.get_feature_names_out())
            valid_indices = [i for i, name in enumerate(feature_names) if len(name) > 1]
            if not valid_indices: return ""

            top_indices = summed_tfidf[valid_indices].argsort()[-top_n:][::-1]
            keywords = [feature_names[valid_indices[i]] for i in top_indices]
            return "_".join(re.sub(r'[\\/:*?"<>|]', '', k) for k in keywords if k)
        except Exception as e:
            logging.error(f"提取主题关键词时出错: {e}")
            return ""

    def _remove_empty_subdirectories(self, path: str) -> None:
        """(清理) 从底向上递归删除指定路径下的所有空子文件夹。"""
        logging.info(f"开始清理目录 '{path}' 下的空文件夹...")
        removed_count = 0
        for dirpath, _, _ in os.walk(path, topdown=False):
            if not os.path.exists(dirpath): continue
            try:
                if not os.listdir(dirpath):
                    os.rmdir(dirpath)
                    logging.info(f"  - 已删除空文件夹: {dirpath}")
                    removed_count += 1
            except OSError as e:
                logging.error(f"无法删除空文件夹 {dirpath}: {e}")
        logging.info(f"空文件夹清理完成，共删除 {removed_count} 个目录。")
