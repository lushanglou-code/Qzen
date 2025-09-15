# -*- coding: utf-8 -*-
"""
单元测试模块：测试数据库操作。
"""

import unittest
import os

# 将项目根目录添加到sys.path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Document


class TestDatabaseHandler(unittest.TestCase):
    """测试 DatabaseHandler 类的功能。"""

    def setUp(self):
        """为每个测试用例初始化一个内存中的SQLite数据库。"""
        # 使用内存SQLite数据库进行快速、隔离的测试
        self.db_handler = DatabaseHandler(db_url="sqlite:///:memory:")
        # 在内存数据库中创建表
        self.db_handler.create_tables()

    def test_document_operations(self):
        """测试针对 Document 模型的增、查、改操作。"""
        # 1. 准备测试数据
        doc1 = Document(file_hash="hash1", file_path="/path/doc1.txt")
        doc2 = Document(file_hash="hash2", file_path="/path/doc2.pdf", feature_vector=b'vector2')
        doc3 = Document(file_hash="hash3", file_path="/path/doc3.docx")
        initial_docs = [doc1, doc2, doc3]

        # 2. 测试批量保存
        self.db_handler.bulk_save_documents(initial_docs)

        # 3. 测试 get_all_documents
        all_docs = self.db_handler.get_all_documents()
        self.assertEqual(len(all_docs), 3)
        # 验证返回的文档哈希值是否正确
        self.assertSetEqual({doc.file_hash for doc in all_docs}, {"hash1", "hash2", "hash3"})

        # 4. 测试 get_documents_without_vectors
        docs_needing_vectors = self.db_handler.get_documents_without_vectors()
        self.assertEqual(len(docs_needing_vectors), 2)
        # 验证返回的是否是向量字段为None的文档
        self.assertSetEqual({doc.file_hash for doc in docs_needing_vectors}, {"hash1", "hash3"})

        # 5. 测试更新操作 (merge)
        # 获取doc1，为其添加向量，然后保存
        doc1_from_db = next(d for d in all_docs if d.file_hash == "hash1")
        self.assertIsNone(doc1_from_db.feature_vector)
        doc1_from_db.feature_vector = b'new_vector1'
        self.db_handler.bulk_save_documents([doc1_from_db])

        # 再次查询，验证向量已更新
        docs_needing_vectors_after_update = self.db_handler.get_documents_without_vectors()
        self.assertEqual(len(docs_needing_vectors_after_update), 1)
        self.assertEqual(docs_needing_vectors_after_update[0].file_hash, "hash3")

        all_docs_after_update = self.db_handler.get_all_documents()
        updated_doc1 = next(d for d in all_docs_after_update if d.file_hash == "hash1")
        self.assertEqual(updated_doc1.feature_vector, b'new_vector1')


if __name__ == '__main__':
    unittest.main()