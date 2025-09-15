# -*- coding: utf-8 -*-
"""
文件系统操作模块。

封装了所有与文件、目录相关的操作，如扫描文件、读取文件内容、计算哈希值等。
这些函数应该是无状态的。
"""

import hashlib
import logging
import os
from typing import Iterator


def scan_files(root_path: str, allowed_extensions: set[str]) -> Iterator[str]:
    """
    递归扫描指定目录下所有符合扩展名要求的文件。

    这是一个生成器函数，会逐一返回找到的文件路径，以节省内存。

    Args:
        root_path: 要扫描的根目录路径。
        allowed_extensions: 一个包含允许的文件后缀的集合 (例如 {'.pdf', '.docx'})。

    Yields:
        符合条件的文件的绝对路径。
    """
    if not os.path.isdir(root_path):
        logging.warning(f"指定的扫描路径不是一个有效目录: {root_path}")
        return

    for dirpath, _, filenames in os.walk(root_path):
        for filename in filenames:
            # 获取文件扩展名，并转为小写以进行不区分大小写的比较
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext in allowed_extensions:
                yield os.path.join(dirpath, filename)


def calculate_file_hash(file_path: str) -> str | None:
    """
    计算单个文件的 SHA-256 哈希值。

    Args:
        file_path: 文件的绝对路径。

    Returns:
        文件的SHA-256哈希值的十六进制字符串。如果文件无法读取，则返回 None。
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # 每次读取 4MB 的块，以处理大文件并节省内存
            for byte_block in iter(lambda: f.read(4096 * 1024), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except (IOError, PermissionError) as e:
        logging.error(f"无法读取文件或计算哈希值: {file_path}, 错误: {e}")
        return None