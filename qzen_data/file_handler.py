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

# 引入所有需要的解析库
import docx
import fitz  # PyMuPDF
import openpyxl
import pptx
import xlrd


def scan_files(root_path: str, allowed_extensions: set[str]) -> Iterator[str]:
    """
    递归扫描指定目录下所有符合扩展名要求的文件。
    """
    if not os.path.isdir(root_path):
        logging.warning(f"指定的扫描路径不是一个有效目录: {root_path}")
        return

    for dirpath, _, filenames in os.walk(root_path):
        for filename in filenames:
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext in allowed_extensions:
                yield os.path.normpath(os.path.join(dirpath, filename))


def calculate_file_hash(file_path: str) -> str | None:
    """
    计算单个文件的 SHA-256 哈希值。
    """
    norm_path = os.path.normpath(file_path)
    sha256_hash = hashlib.sha256()
    try:
        with open(norm_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096 * 1024), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except (IOError, PermissionError) as e:
        logging.error(f"无法读取文件或计算哈希值: {norm_path}, 错误: {e}")
        return None


def get_content_slice(file_path: str, slice_size_kb: int = 1) -> str:
    """
    提取并返回一个文档的内容切片（开头和结尾）。
    """
    norm_path = os.path.normpath(file_path)
    file_ext = os.path.splitext(norm_path)[1].lower()
    text_content = ""

    try:
        if file_ext in ('.txt', '.md'):
            with open(norm_path, 'r', encoding='utf-8', errors='ignore') as f:
                text_content = f.read()
        elif file_ext == '.pdf':
            with fitz.open(norm_path) as doc:
                for page in doc:
                    text_content += page.get_text()
        elif file_ext == '.docx':
            doc = docx.Document(norm_path)
            for para in doc.paragraphs:
                text_content += para.text + '\n'
        elif file_ext == '.pptx':
            prs = pptx.Presentation(norm_path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text_content += shape.text + '\n'
        elif file_ext == '.xlsx':
            workbook = openpyxl.load_workbook(norm_path, read_only=True)
            for sheet in workbook.worksheets:
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value:
                            text_content += str(cell.value) + ' '
                    text_content += '\n'
        elif file_ext == '.xls':
            workbook = xlrd.open_workbook(norm_path)
            for sheet in workbook.sheets():
                for row_idx in range(sheet.nrows):
                    for col_idx in range(sheet.ncols):
                        cell_value = sheet.cell_value(row_idx, col_idx)
                        if cell_value:
                            text_content += str(cell_value) + ' '
                    text_content += '\n'
        elif file_ext == '.ppt':
            logging.warning(f"'.ppt' (旧版PowerPoint) 文件是二进制格式，当前版本无法直接提取其文本内容。将跳过文件: {norm_path}")
            return ""

    except Exception as e:
        logging.error(f"无法从文件提取文本内容: {norm_path}, 错误: {e}")
        return ""

    slice_size = slice_size_kb * 1024
    if len(text_content) <= slice_size * 2:
        return text_content

    head = text_content[:slice_size]
    tail = text_content[-slice_size:]

    return head + "\n...\n" + tail
