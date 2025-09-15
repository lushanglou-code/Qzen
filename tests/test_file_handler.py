# -*- coding: utf-8 -*-
"""
单元测试模块：测试文件系统操作。
"""

import os
import shutil
import tempfile
import unittest

import docx
import fitz  # PyMuPDF

# 将项目根目录添加到sys.path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qzen_data import file_handler


class TestFileHandler(unittest.TestCase):
    """测试 file_handler 模块中的函数。"""

    def setUp(self):
        """创建一个临时目录用于存放测试文件。"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """删除临时目录及其所有内容。"""
        shutil.rmtree(self.test_dir)

    def test_get_content_slice_long_txt(self):
        """测试从一个长文本文件中提取内容切片。"""
        file_path = os.path.join(self.test_dir, "long.txt")
        # 创建一个超过2KB的文本内容
        head_content = "a" * 1024
        middle_content = "b" * 2048
        tail_content = "c" * 1024
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(head_content + middle_content + tail_content)

        slice_content = file_handler.get_content_slice(file_path, slice_size_kb=1)
        
        expected_content = head_content + "\n...\n" + tail_content
        self.assertEqual(slice_content, expected_content)

    def test_get_content_slice_short_txt(self):
        """测试一个短文本文件（小于2KB），应返回全部内容。"""
        file_path = os.path.join(self.test_dir, "short.txt")
        content = "This is a short text." * 10
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        slice_content = file_handler.get_content_slice(file_path, slice_size_kb=1)
        self.assertEqual(slice_content, content)

    def test_get_content_slice_docx(self):
        """测试从 .docx 文件中提取内容切片。"""
        file_path = os.path.join(self.test_dir, "test.docx")
        doc = docx.Document()
        head_content = "This is the header. " * 200 # 确保内容足够长
        tail_content = "This is the footer. " * 200
        doc.add_paragraph(head_content)
        doc.add_paragraph("This is the middle.")
        doc.add_paragraph(tail_content)
        doc.save(file_path)

        slice_content = file_handler.get_content_slice(file_path, slice_size_kb=1)
        
        # 从原始文本中提取预期的切片
        full_text = head_content + "\n" + "This is the middle." + "\n" + tail_content + "\n"
        expected_head = full_text[:1024]
        expected_tail = full_text[-1024:]
        expected_slice = expected_head + "\n...\n" + expected_tail

        self.assertEqual(slice_content, expected_slice)

    def test_get_content_slice_pdf(self):
        """测试从 .pdf 文件中提取内容切片。"""
        file_path = os.path.join(self.test_dir, "test.pdf")
        doc = fitz.open() # 创建一个空的PDF
        head_content = "This is the PDF header. " * 200
        tail_content = "This is the PDF footer. " * 200
        full_text = head_content + "\nThis is the middle.\n" + tail_content
        
        # 创建一个页面并插入文本
        page = doc.new_page()
        page.insert_text((50, 72), full_text, fontsize=11)
        doc.save(file_path)
        doc.close()

        slice_content = file_handler.get_content_slice(file_path, slice_size_kb=1)
        
        expected_head = full_text[:1024]
        expected_tail = full_text[-1024:]
        expected_slice = expected_head + "\n...\n" + expected_tail
        
        self.assertEqual(slice_content, expected_slice)

    def test_get_content_slice_nonexistent_file(self):
        """测试当文件不存在时，函数应返回空字符串。"""
        file_path = os.path.join(self.test_dir, "nonexistent.txt")
        slice_content = file_handler.get_content_slice(file_path)
        self.assertEqual(slice_content, "")


if __name__ == '__main__':
    unittest.main()