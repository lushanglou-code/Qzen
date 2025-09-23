# -*- coding: utf-8 -*-
"""
日志系统配置模块 (v1.2 - 最终修复版)。

此版本彻底修复了因不当使用 `logging.basicConfig` 导致的日志系统静默失败问题。
旧的实现会在 `main.py` 隐式创建默认 handler 后失效，导致文件 handler 从未被注册。

新的实现遵循 `logging` 模块的最佳实践：
1.  直接获取根记录器 (root logger)。
2.  清空其上所有已存在的 handlers，确保配置的幂等性。
3.  显式地创建、配置并添加 `StreamHandler` 和 `RotatingFileHandler`。

这确保了无论在何处、何时调用，日志系统都能被正确、健壮地初始化，
从而保证所有线程的日志都能被统一捕获到控制台和文件。
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logging() -> None:
    """
    配置全局的根日志记录器 (root logger)。
    """
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, "qzen_app.log")
    
    # 定义统一的日志格式
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s')

    # --- 创建并配置 Handlers ---
    # 控制台 Handler
    stream_handler = logging.StreamHandler(sys.stdout) # 明确指定输出到标准输出
    stream_handler.setFormatter(log_format)

    # 文件 Handler (循环写入)
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=5*1024*1024, # 5 MB
        backupCount=5, 
        encoding='utf-8'
    )
    file_handler.setFormatter(log_format)

    # --- 配置根记录器 (Root Logger) ---
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) # 设置全局最低日志级别

    # 关键修复：清空所有现有的 handlers，确保从干净的状态开始配置
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 为根记录器添加我们新创建的 handlers
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    # --- 调整特定库的日志级别，保持输出整洁 ---
    logging.getLogger("jieba").setLevel(logging.INFO)
    logging.getLogger("PIL").setLevel(logging.INFO)
    logging.getLogger("matplotlib").setLevel(logging.INFO)

    logging.info("日志系统 (v1.2) 已成功配置，所有日志将同步输出到控制台和文件。")
