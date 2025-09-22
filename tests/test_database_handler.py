# -*- coding: utf-8 -*-
"""
测试单元：数据库操作模块 (v3.3)

此测试验证 DatabaseHandler 的核心功能，特别是新增的按路径查询方法，
并验证了在真实 DM8 数据库上的批量插入性能。
"""

import unittest
import os

# 尝试导入 dmPython，以便在测试中检查其可用性
try:
    import dmPython
except ImportError:
    dmPython = None

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
        mock_doc = Document(
            id=1,
            file_hash="abcde",
            file_path=self.test_path,
            content_slice="Hello world"
        )
        with self.db_handler.get_session() as session:
            session.add(mock_doc)
            session.commit()

    def test_get_document_by_path_success(self):
        """
        测试 get_document_by_path 在路径存在时能否成功返回文档。
        """
        # 调用被测试的方法
        found_doc = self.db_handler.get_document_by_path(self.test_path)

        # 断言返回了对象，并且其属性与我们存入的一致
        # v3.3 修正: 不再与游离对象 (detached instance) 的属性比较，
        # 而是直接与已知的字面值比较，以避免 DetachedInstanceError。
        self.assertIsNotNone(found_doc)
        self.assertEqual(found_doc.id, 1)
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

    @unittest.skipIf(dmPython is None, "dmPython 库未安装，跳过 DM8 数据库测试。")
    def test_bulk_insert_documents_with_sqlalchemy_batch(self):
        """
        测试 SQLAlchemy 的 add_all 是否能在 dm8 上成功执行批量插入。
        这个测试验证了新的、高效的批量插入策略是有效的。
        """
        # 1. 定义 DM8 连接参数
        DM_USER = "GIMI"
        DM_PASSWORD = "DM8DM8DM8"
        DM_SERVER = "127.0.0.1"
        DM_PORT = 5236
        db_url = f"dm+dmPython://{DM_USER}:{DM_PASSWORD}@{DM_SERVER}:{DM_PORT}/"

        # 2. 检查是否可以连接，如果不能，跳过测试
        try:
            conn = dmPython.connect(user=DM_USER, password=DM_PASSWORD, server=DM_SERVER, port=DM_PORT, autoCommit=False)
            conn.close()
        except dmPython.Error as e:
            self.skipTest(f"无法连接到 DM8 数据库，跳过此测试: {e}")

        # 3. 使用 DM8 连接重新配置 DatabaseHandler
        dm8_handler = DatabaseHandler(db_url)
        dm8_handler.recreate_tables()

        # 4. 准备批量插入的数据
        docs_to_insert = [
            Document(file_hash="batch_hash_1", file_path="/path/batch/1.txt", content_slice="batch 1"),
            Document(file_hash="batch_hash_2", file_path="/path/batch/2.txt", content_slice="batch 2"),
            Document(file_hash="batch_hash_3", file_path="/path/batch/3.txt", content_slice="batch 3"),
        ]
        
        # 5. 执行批量插入 (这是被测试的核心逻辑)
        try:
            dm8_handler.bulk_insert_documents(docs_to_insert)
        except Exception as e:
            self.fail(f"调用优化的 bulk_insert_documents 时失败，抛出异常: {e}")

        # 6. 验证数据是否已成功插入
        with dm8_handler.get_session() as session:
            count = session.query(Document).filter(Document.file_hash.like('batch_hash_%')).count()
            self.assertEqual(count, len(docs_to_insert), "批量插入后数据库中的记录数与预期不符")

        # 7. 清理测试数据
        with dm8_handler.get_session() as session:
            session.query(Document).filter(Document.file_hash.like('batch_hash_%')).delete(synchronize_session=False)
            session.commit()

if __name__ == '__main__':
    unittest.main()
