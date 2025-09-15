# -*- coding: utf-8 -*-
"""
业务流程协调器模块。

定义了 Orchestrator 类，作为业务逻辑层的“总指挥”，负责协调
数据访问层和各个业务引擎，以完成一个完整的用户请求流程。
"""

import logging
import os
import shutil
from typing import Callable

from qzen_data import file_handler, database_handler


class Orchestrator:
    """
    协调各个模块以完成复杂的业务流程。
    """
    def __init__(self, db_handler: database_handler.DatabaseHandler):
        """初始化协调器。"""
        self.db_handler = db_handler

    def run_deduplication(
        self,
        source_path: str,
        intermediate_path: str,
        allowed_extensions: set[str],
        progress_callback: Callable[[int, int, str], None]
    ) -> None:
        """
        执行文档去重流程。

        扫描源文件夹，计算文件哈希，并将唯一文件复制到中间文件夹。

        Args:
            source_path: 源文件夹路径。
            intermediate_path: 中间文件夹路径。
            allowed_extensions: 允许的文件扩展名集合。
            progress_callback: 用于报告进度的回调函数。
                               它接收 (当前值, 最大值, 状态文本)。
        """
        logging.info(f"开始去重流程: 源='{source_path}', 中间='{intermediate_path}'")
        os.makedirs(intermediate_path, exist_ok=True)

        # 扫描文件并转换为列表以获取总数
        files_to_scan = list(file_handler.scan_files(source_path, allowed_extensions))
        total_files = len(files_to_scan)
        processed_hashes = set()

        for i, file_path in enumerate(files_to_scan):
            progress_callback(i + 1, total_files, f"正在处理: {os.path.basename(file_path)}")
            file_hash = file_handler.calculate_file_hash(file_path)

            if file_hash and file_hash not in processed_hashes:
                processed_hashes.add(file_hash)

                # --- 复制唯一文件到中间目录，并保持其相对目录结构 ---
                # 计算文件相对于源文件夹的路径
                relative_path = os.path.relpath(file_path, source_path)
                destination_path = os.path.join(intermediate_path, relative_path)

                # 创建目标文件的父目录（如果不存在）
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)

                # TODO: 后续将结合数据库检查，避免重复复制
                shutil.copy2(file_path, destination_path)
                logging.debug(f"复制唯一文件: {file_path} -> {destination_path}")

        progress_callback(total_files, total_files, "去重完成！")
        logging.info("去重流程结束。")