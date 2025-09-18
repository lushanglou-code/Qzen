# -*- coding: utf-8 -*-
"""
日志系统配置模块。

提供一个统一的函数 `setup_logging` 来配置应用程序全局的日志记录器。
通过在程序启动时调用此单一函数，可以确保所有模块的日志行为一致。
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging() -> None:
    """
    配置全局的根日志记录器 (root logger)。

    此函数执行以下操作：
        1.  确保 `logs` 目录存在，用于存放日志文件。
        2.  设置一个 `RotatingFileHandler`，它会自动管理日志文件的大小。
            当日志文件达到1MB时，它会被重命名备份，并创建一个新的日志文件。
            最多会保留5个备份文件。
        3.  定义一个标准的日志格式，包含时间、记录器名称、日志级别和消息内容。
        4.  使用 `logging.basicConfig` 来应用配置，将日志同时输出到
            控制台 (StreamHandler) 和文件 (RotatingFileHandler)。
    """
    log_dir = "logs"
    # 确保日志文件存放的目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 创建一个循环写入的日志文件处理器。
    # 每个文件最大1MB，当超过大小时，会创建新的，最多保留5个旧的备份文件。
    log_file = os.path.join(log_dir, "qzen_app.log")
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=1*1024*1024, # 1 MB
        backupCount=5, 
        encoding='utf-8'
    )
    
    # 定义所有日志消息的格式。
    # asctime: 日志记录时间
    # name: 日志记录器的名称 (例如，'qzen_core.orchestrator')
    # levelname: 日志级别 (例如，INFO, WARNING, ERROR)
    # message: 实际的日志消息
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(log_format)

    # 使用 basicConfig 对根记录器进行一次性配置。
    # 这会移除所有现有的处理器并添加这里指定的处理器。
    logging.basicConfig(
        level=logging.DEBUG,  # 设置根记录器处理的最低日志级别为 DEBUG
        handlers=[
            logging.StreamHandler(),  # 将日志输出到标准错误流（通常是控制台）
            file_handler              # 将日志输出到文件
        ]
    )
