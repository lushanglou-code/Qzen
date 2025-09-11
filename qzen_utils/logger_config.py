# -*- coding: utf-8 -*-
"""
日志系统配置模块。

提供一个函数来配置全局的日志记录器。
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging() -> None:
    """
    配置全局日志系统。

    将日志同时输出到控制台和文件中，并设置日志格式。
    """
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 创建一个循环写入的日志文件处理器，每个文件最大1MB，保留5个备份
    log_file = os.path.join(log_dir, "qzen_app.log")
    file_handler = RotatingFileHandler(log_file, maxBytes=1*1024*1024, backupCount=5, encoding='utf-8')
    
    # 定义日志格式
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(log_format)

    # 获取根日志记录器，设置级别并添加处理器
    logging.basicConfig(
        level=logging.DEBUG,  # 记录所有级别的日志
        handlers=[
            logging.StreamHandler(),  # 输出到控制台
            file_handler              # 输出到文件
        ]
    )