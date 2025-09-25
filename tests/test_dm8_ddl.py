# tests/test_dm8_ddl.py

import unittest
import os
from sqlalchemy import create_engine, inspect
from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Base, TaskRun, Document, DeduplicationResult

# 使用一个内存中的SQLite数据库进行快速、隔离的测试
# 如果需要针对DM8进行测试，可以将此URL更改为DM8的连接字符串
# TEST_DB_URL = "dm+dmPython://GIMI:DM8DM8DM8@127.0.0.1:5236/"
TEST_DB_URL = "sqlite:///:memory:"


class TestDM8DDL(unittest.TestCase):
    """
    一个独立的测试单元，专门用于验证 `recreate_tables` 方法
    是否能够稳定、可靠地清空和重建所有数据库表。
    """

    def setUp(self):
        """在每个测试前执行"""
        self.db_handler = DatabaseHandler(db_url=TEST_DB_URL, echo=True)
        self.engine = self.db_handler._get_engine()

    def tearDown(self):
        """在每个测试后执行"""
        self.engine.dispose()

    def test_recreate_tables_works_flawlessly(self):
        """
        测试: recreate_tables 是否能处理一个已经包含数据的数据库。

        步骤:
        1. 第一次调用 recreate_tables() 创建一个干净的数据库结构。
        2. 验证所有表都已创建。
        3. (模拟一次运行) 在表中插入一些数据。
        4. 第二次调用 recreate_tables()。这是测试的关键，它必须能
           在存在数据和外键约束的情况下，成功清空所有内容。
        5. 再次验证所有表都存在，并且为空。
        """
        inspector = inspect(self.engine)
        table_names = set(Base.metadata.tables.keys())

        # --- 第一次创建 ---
        print("\\n--- 第一次调用 recreate_tables ---")
        self.db_handler.recreate_tables()

        # 验证所有表都已创建
        self.assertEqual(set(inspector.get_table_names()), table_names)
        print("--- 验证成功: 所有表已创建 ---")

        # --- 插入模拟数据 ---
        with self.db_handler.get_session() as session:
            task = TaskRun(task_type="test")
            session.add(task)
            session.commit()
            doc = Document(file_hash="test_hash", file_path="/test/path")
            session.add(doc)
            session.commit()
            result = DeduplicationResult(task_run_id=task.id, duplicate_file_path="/dup/path",
                                         original_file_hash="hash")
            session.add(result)
            session.commit()
        print("--- 模拟数据已插入 ---")

        # --- 第二次调用 (关键测试) ---
        print("\\n--- 第二次调用 recreate_tables (关键测试) ---")
        try:
            self.db_handler.recreate_tables()
        except Exception as e:
            self.fail(f"第二次调用 recreate_tables 时发生致命错误，数据库清空失败: {e}")

        # --- 再次验证 ---
        # v4.2.8 修复: 使用 inspector.reflect_table() 来清除缓存并重新加载所有元数据
        for table_name in table_names:
            inspector.reflect_table(Base.metadata.tables[table_name], None)
        self.assertEqual(set(inspector.get_table_names()), table_names)
        print("--- 验证成功: 所有表被成功重建 ---")

        # 验证表是空的
        with self.db_handler.get_session() as session:
            for table in Base.metadata.tables.values():
                count = session.query(table).count()
                self.assertEqual(count, 0, f"表 {table.name} 在重建后不为空，仍有 {count} 条数据。")
        print("--- 验证成功: 所有表都为空 ---")
        print("\\nDDL 测试通过！")


if __name__ == '__main__':
    unittest.main()