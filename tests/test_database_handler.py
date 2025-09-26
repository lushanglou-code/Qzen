# -*- coding: utf-8 -*-
"""
测试单元：数据库操作模块 (v5.4.1)。

此版本修复了 `test_get_document_by_path_success` 中的一个路径断言错误。
该错误源于应用逻辑会将路径统一为正斜杠 (/) 存入数据库，而测试代码
在 Windows 上会生成反斜杠 (\\) 路径，导致查询不匹配。

修复方案是确保测试中存入和查询的路径都使用正斜杠，以模拟真实行为。
"""

import unittest
import os
from sqlalchemy import inspect

from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Base, Document, TaskRun, DeduplicationResult


class TestDatabaseHandler(unittest.TestCase):
    """
    测试 DatabaseHandler 的数据库交互。
    """

    def setUp(self):
        """在每个测试前，配置一个临时的内存数据库。"""
        self.db_handler = DatabaseHandler('sqlite:///:memory:')
        self.engine = self.db_handler._get_engine()  # 获取内部引擎用于检查
        self.db_handler.recreate_tables()

        # v5.4.1 修复: 确保测试中使用的路径是正斜杠格式，以匹配应用层的存储逻辑
        self.test_path = "/path/to/my/document.txt"
        mock_doc = Document(
            id=1,
            file_hash="abcde",
            file_path=self.test_path, # 使用正斜杠路径
            content_slice="Hello world"
        )
        with self.db_handler.get_session() as session:
            session.add(mock_doc)
            session.commit()

    def tearDown(self):
        """在每个测试后执行"""
        self.engine.dispose()

    def test_get_document_by_path_success(self):
        """
        测试 get_document_by_path 在路径存在时能否成功返回文档。
        """
        # 使用相同的正斜杠路径进行查询
        found_doc = self.db_handler.get_document_by_path(self.test_path)
        self.assertIsNotNone(found_doc, "文档应该被找到，但返回了 None")
        self.assertEqual(found_doc.id, 1)
        self.assertEqual(found_doc.file_path, self.test_path)

    def test_get_document_by_path_not_found(self):
        """
        测试 get_document_by_path 在路径不存在时是否返回 None。
        """
        # 查询一个不存在的路径
        non_existent_path = "/path/to/non/existent.file"
        found_doc = self.db_handler.get_document_by_path(non_existent_path)
        self.assertIsNone(found_doc)

    def test_recreate_tables_is_robust(self):
        """
        测试: recreate_tables 是否能处理一个已经包含数据的数据库。
        """
        inspector = inspect(self.engine)
        table_names = set(Base.metadata.tables.keys())

        with self.db_handler.get_session() as session:
            task = TaskRun(task_type="test")
            session.add(task)
            session.commit()
            doc = Document(file_hash="test_hash_2", file_path="/test/path/2")
            session.add(doc)
            session.commit()
            result = DeduplicationResult(task_run_id=task.id, duplicate_file_path="/dup/path",
                                         original_file_hash="hash")
            session.add(result)
            session.commit()

        try:
            self.db_handler.recreate_tables()
        except Exception as e:
            self.fail(f"第二次调用 recreate_tables 时发生致命错误，数据库清空失败: {e}")

        self.assertEqual(set(inspector.get_table_names()), table_names, "重建后部分表丢失")

        with self.db_handler.get_session() as session:
            for table in Base.metadata.tables.values():
                count = session.query(table).count()
                self.assertEqual(count, 0, f"表 {table.name} 在重建后不为空，仍有 {count} 条数据。")


if __name__ == '__main__':
    unittest.main()
