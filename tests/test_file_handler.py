# -*- coding: utf-8 -*-
"""
单元测试模块：测试文件系统操作 (v5.4.2)。

此版本修复了 `get_content_slice` 的长文本测试用例。原先的测试
在内部重新实现了切片逻辑来生成预期结果，这种做法容易出错。新的
测试改用一个结构简单、可精确预测的输入，并与一个手动计算出的、
确定的预期输出进行比较，从而使测试更加健壮和可靠。
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import docx

# 将项目根目录添加到sys.path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qzen_data import file_handler
from qzen_data.file_handler import _clean_text


class TestFileHandler(unittest.TestCase):
    """测试 file_handler 模块中的函数。"""

    def setUp(self):
        """创建一个临时目录用于存放测试文件。"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """删除临时目录及其所有内容。"""
        shutil.rmtree(self.test_dir)

    def test_get_content_slice_long_txt(self):
        """v5.4.2 修复: 测试从一个长文本文件中提取内容切片（> 6KB）。"""
        file_path = os.path.join(self.test_dir, "long.txt")
        part_size = 2 * 1024

        # 构造一个总长7000的、结构简单的文本
        text = ('a' * part_size) + ('b' * 2904) + ('c' * part_size)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

        # 手动精确计算预期的三段式摘要
        head_expected = 'a' * part_size
        tail_expected = 'c' * part_size
        # middle_start = (7000 - 2048) // 2 = 2476. The slice is [2476:4524]
        # This slice is entirely within the 'b' part.
        middle_expected = 'b' * part_size
        expected_output = f"{head_expected}\n... (中间部分) ...\n{middle_expected}\n... (结尾部分) ...\n{tail_expected}"

        actual_output = file_handler.get_content_slice(file_path)
        self.assertEqual(actual_output, expected_output)

    def test_get_content_slice_short_txt(self):
        """测试一个短文本文件（< 6KB），应返回全部内容。"""
        file_path = os.path.join(self.test_dir, "short.txt")
        content = "This is a short text." * 10
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        slice_content = file_handler.get_content_slice(file_path)
        expected_content = _clean_text(content)
        self.assertEqual(slice_content, expected_content)

    @patch('qzen_data.file_handler.fitz.open')
    def test_get_content_slice_pdf(self, mock_fitz_open):
        """v5.4.2 修复: 测试从 .pdf 文件中提取内容切片，使用简化的模拟数据。"""
        part_size = 2 * 1024
        text = ('a' * part_size) + ('b' * 2904) + ('c' * part_size)

        # 手动精确计算预期的三段式摘要
        head_expected = 'a' * part_size
        tail_expected = 'c' * part_size
        middle_expected = 'b' * part_size
        expected_output = f"{head_expected}\n... (中间部分) ...\n{middle_expected}\n... (结尾部分) ...\n{tail_expected}"

        mock_page = MagicMock()
        mock_page.get_text.return_value = text
        mock_doc = MagicMock()
        mock_doc.__iter__.return_value = [mock_page]
        mock_fitz_open.return_value.__enter__.return_value = mock_doc

        dummy_file_path = "/any/dummy/path/to/a.pdf"
        actual_slice = file_handler.get_content_slice(dummy_file_path)

        self.assertEqual(actual_slice, expected_output)

    def test_get_content_slice_nonexistent_file(self):
        """测试当文件不存在时，函数应返回空字符串。"""
        file_path = os.path.join(self.test_dir, "nonexistent.txt")
        slice_content = file_handler.get_content_slice(file_path)
        self.assertEqual(slice_content, "")


if __name__ == '__main__':
    unittest.main()
