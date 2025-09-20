# -*- coding: utf-8 -*-
"""
测试单元：数据库操作模块 (v3.2)

此测试验证 DatabaseHandler 的核心功能，特别是新增的按路径查询方法。
"""

import unittest
import os

from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Document

class TestDatabaseHandler(unittest.TestCase):
    """
    测试 DatabaseHandler 的数据库交互。
    """

    def setUp(self):
        """在每个测试前，配置一个临时的内存数据库。"""
        self.db_handler = DatabaseHandler('sqlite:///:memory:')
        self.db_handler.recreate_tables()

        # 添加一个模拟文档用于测试
        self.test_path = os.path.normpath("/path/to/my/document.txt")
        self.mock_doc = Document(
            id=1,
            file_hash="abcde",
            file_path=self.test_path,
            content_slice="Hello world"
        )
        with self.db_handler.get_session() as session:
            session.add(self.mock_doc)
            session.commit()

    def test_get_document_by_path_success(self):
        """
        测试 get_document_by_path 在路径存在时能否成功返回文档。
        """
        # 调用被测试的方法
        found_doc = self.db_handler.get_document_by_path(self.test_path)

        # 断言返回了对象，并且其属性与我们存入的一致
        self.assertIsNotNone(found_doc)
        self.assertEqual(found_doc.id, self.mock_doc.id)
        self.assertEqual(found_doc.file_path, self.test_path)

    def test_get_document_by_path_not_found(self):
        """
        测试 get_document_by_path 在路径不存在时是否返回 None。
        """
        # 使用一个不存在的路径调用方法
        non_existent_path = os.path.normpath("/path/to/non/existent.file")
        found_doc = self.db_handler.get_document_by_path(non_existent_path)

        # 断言返回值为 None
        self.assertIsNone(found_doc)

if __name__ == '__main__':
    unittest.main()
