# -*- coding: utf-8 -*-
"""
配置管理模块。

提供保存和加载应用程序配置的功能，使用JSON文件作为持久化存储。
"""

import json
import logging
import os

# 定义配置文件的名称和路径（存储在项目根目录）
CONFIG_FILE_PATH = "config.json"


def save_config(config_data: dict) -> None:
    """
    将配置字典保存到JSON文件中。

    Args:
        config_data: 包含应用程序配置的字典。
    """
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        logging.info(f"配置已成功保存到 {CONFIG_FILE_PATH}")
    except IOError as e:
        logging.error(f"无法写入配置文件 {CONFIG_FILE_PATH}: {e}")


def load_config() -> dict:
    """
    从JSON文件中加载配置。

    Returns:
        一个包含配置数据的字典。如果文件不存在或为空，则返回一个空字典。
    """
    if not os.path.exists(CONFIG_FILE_PATH):
        logging.info(f"配置文件 {CONFIG_FILE_PATH} 不存在，将使用默认配置。")
        return {}

    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            logging.info(f"配置已从 {CONFIG_FILE_PATH} 加载。")
            return config_data
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"无法读取或解析配置文件 {CONFIG_FILE_PATH}: {e}")
        return {}
