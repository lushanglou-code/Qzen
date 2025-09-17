# -*- coding: utf-8 -*-
"""
配置管理模块。

提供保存和加载应用程序配置的通用函数。此模块使用一个简单的、
人类可读的 JSON 文件 (`config.json`) 作为持久化存储。

它与 `qzen_ui.config_dialog` 中使用的 `QSettings` 分工如下：
- `config_manager.py`: 用于存储与项目和UI状态相关的非敏感信息，
  如源/目标文件夹路径、上次使用的关键词等。这些配置是可移植的。
- `QSettings`: 用于存储特定于本地环境的、可能敏感的配置，如数据库
  连接凭据。这些配置通常不应随项目一起分发。
"""

import json
import logging
import os

# 定义配置文件的名称和路径（存储在项目根目录）
CONFIG_FILE_PATH = "config.json"


def save_config(config_data: dict) -> None:
    """
    将配置字典序列化并保存到 JSON 文件中。

    为了方便用户查看和手动编辑，文件被保存为格式化的 JSON。

    Args:
        config_data: 一个包含应用程序配置的字典。
    """
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            # 使用 indent=4 来创建带缩进的、人类可读的JSON文件
            # ensure_ascii=False 确保中文字符能被正确写入
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        logging.info(f"配置已成功保存到 {CONFIG_FILE_PATH}")
    except IOError as e:
        logging.error(f"无法写入配置文件 {CONFIG_FILE_PATH}: {e}")


def load_config() -> dict:
    """
    从 JSON 文件中加载配置并返回一个字典。

    此函数被设计为健壮的：如果配置文件不存在、为空或包含无效的JSON，
    它将记录一个错误并返回一个空字典。这可以确保即使在配置丢失或损坏
    的情况下，应用程序也能以默认状态启动，而不会崩溃。

    Returns:
        一个包含从文件中加载的配置数据的字典。如果失败，则返回一个空字典。
    """
    # 如果配置文件不存在，直接返回空字典，让调用方处理默认值
    if not os.path.exists(CONFIG_FILE_PATH):
        logging.info(f"配置文件 {CONFIG_FILE_PATH} 不存在，将使用默认配置。")
        return {}

    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            # 确保即使文件是空的，也返回一个字典
            if config_data is None:
                return {}
            logging.info(f"配置已从 {CONFIG_FILE_PATH} 加载。")
            return config_data
    except (json.JSONDecodeError, IOError) as e:
        # 如果文件损坏（无效JSON）或无法读取，记录错误并返回空字典
        logging.error(f"无法读取或解析配置文件 {CONFIG_FILE_PATH}: {e}")
        return {}
