# -*- coding: utf-8 -*-
"""
文件系统操作模块。

封装了所有与文件、目录相关的底层操作，如扫描文件、读取文件内容、
计算哈希值等。此模块中的所有函数都应设计为无状态的纯函数，不依
赖于任何外部状态或类实例。
"""

import hashlib
import logging
import os
from typing import Iterator

# --- 引入所有需要的第三方文档解析库 ---
import docx
import fitz  # PyMuPDF，用于解析PDF
import openpyxl
import pptx
import xlrd


def scan_files(root_path: str, allowed_extensions: set[str]) -> Iterator[str]:
    """
    递归扫描指定目录下所有符合扩展名要求的文件。

    Args:
        root_path: 需要扫描的根目录路径。
        allowed_extensions: 一个包含允许的文件扩展名的集合，例如 {'.txt', '.pdf'}。
                          扩展名需要包含点 `.` 且为小写。

    Yields:
        一个迭代器，每次返回一个符合条件的文件的完整、规范化的路径字符串。
    """
    if not os.path.isdir(root_path):
        logging.warning(f"指定的扫描路径不是一个有效目录: {root_path}")
        return

    for dirpath, _, filenames in os.walk(root_path):
        for filename in filenames:
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext in allowed_extensions:
                # 使用 os.path.normpath 确保路径格式在不同操作系统上的一致性
                yield os.path.normpath(os.path.join(dirpath, filename))


def calculate_file_hash(file_path: str) -> str | None:
    """
    计算单个文件的 SHA-256 哈希值。

    为了在处理大文件时避免一次性将整个文件读入内存，此函数采用分块
    读取的方式，提高了内存效率。

    Args:
        file_path: 目标文件的完整路径。

    Returns:
        如果成功，返回文件的 SHA-256 哈希值的十六进制字符串。
        如果发生文件读取错误（如文件不存在、无权限），则返回 None。
    """
    norm_path = os.path.normpath(file_path)
    sha256_hash = hashlib.sha256()
    try:
        with open(norm_path, "rb") as f:
            # 以 4MB 的块大小迭代读取文件，适用于大文件处理
            for byte_block in iter(lambda: f.read(4096 * 1024), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except (IOError, PermissionError) as e:
        logging.error(f"无法读取文件或计算哈希值: {norm_path}, 错误: {e}")
        return None


def get_content_slice(file_path: str, slice_size_kb: int = 1) -> str:
    """
    提取并返回一个文档的内容切片（开头和结尾部分）。

    此函数是实现文档相似度评估的关键。通过仅提取文档的首尾部分作为
    其内容的摘要，可以在不牺牲过多代表性的前提下，大幅提升后续特征
    提取（向量化）的计算效率。

    支持的格式:
        - .txt, .md (纯文本)
        - .pdf (使用 PyMuPDF/fitz)
        - .docx (使用 python-docx)
        - .pptx (使用 python-pptx)
        - .xlsx (使用 openpyxl)
        - .xls (使用 xlrd)

    不支持的格式:
        - .ppt (旧版PowerPoint二进制格式)

    切片逻辑:
        如果提取的文本总长度小于等于 `slice_size_kb * 2` KB，则返回全部内容。
        否则，返回开头 `slice_size_kb` KB 和结尾 `slice_size_kb` KB 的内容，
        中间用 "\n...\n" 分隔。

    Args:
        file_path: 目标文件的完整路径。
        slice_size_kb: 定义切片大小的单位（KB），默认为 1 KB。

    Returns:
        提取出的文本内容切片字符串。如果文件无法解析或不受支持，则返回空字符串。
    """
    norm_path = os.path.normpath(file_path)
    file_ext = os.path.splitext(norm_path)[1].lower()
    text_content = ""

    try:
        # --- 根据文件扩展名选择不同的解析策略 ---
        if file_ext in ('.txt', '.md'):
            # 对于纯文本，直接读取
            with open(norm_path, 'r', encoding='utf-8', errors='ignore') as f:
                text_content = f.read()

        elif file_ext == '.pdf':
            # 使用 PyMuPDF (fitz) 解析 .pdf 文件
            with fitz.open(norm_path) as doc:
                for page in doc:
                    text_content += page.get_text()

        elif file_ext == '.docx':
            # 使用 python-docx 解析 .docx 文件
            doc = docx.Document(norm_path)
            for para in doc.paragraphs:
                text_content += para.text + '\n'

        elif file_ext == '.pptx':
            # 使用 python-pptx 解析 .pptx 文件
            prs = pptx.Presentation(norm_path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text_content += shape.text + '\n'

        elif file_ext == '.xlsx':
            # 使用 openpyxl 解析 .xlsx 文件 (现代Excel格式)
            workbook = openpyxl.load_workbook(norm_path, read_only=True)
            for sheet in workbook.worksheets:
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value:
                            text_content += str(cell.value) + ' '
                    text_content += '\n'

        elif file_ext == '.xls':
            # 使用 xlrd 解析 .xls 文件 (旧版Excel格式)
            workbook = xlrd.open_workbook(norm_path)
            for sheet in workbook.sheets():
                for row_idx in range(sheet.nrows):
                    for col_idx in range(sheet.ncols):
                        cell_value = sheet.cell_value(row_idx, col_idx)
                        if cell_value:
                            text_content += str(cell_value) + ' '
                    text_content += '\n'

        elif file_ext == '.ppt':
            # .ppt 是复杂的二进制格式，当前版本不予支持
            logging.warning(f"'.ppt' (旧版PowerPoint) 文件是二进制格式，当前版本无法直接提取其文本内容。将跳过文件: {norm_path}")
            return ""

    except Exception as e:
        # 捕获所有可能的解析异常，保证单个文件的失败不影响整个流程
        logging.error(f"无法从文件提取文本内容: {norm_path}, 错误: {e}")
        return ""

    # --- 执行切片逻辑 ---
    slice_size = slice_size_kb * 1024
    if len(text_content) <= slice_size * 2:
        return text_content

    head = text_content[:slice_size]
    tail = text_content[-slice_size:]

    return head + "\n...\n" + tail
