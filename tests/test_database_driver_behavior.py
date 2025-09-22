# -*- coding: utf-8 -*-
"""
数据库驱动行为的真实集成测试 (v3.3.2 最终版)。

此测试文件不使用任何模拟（Mock），它直接连接到真实的DM8数据库，
旨在精确地、可重复地证明和验证 `sqlalchemy-dm` 驱动在不同写入
场景下的行为，并验证我们针对其 Bug 的变通方案是有效的。
"""

import pytest
import logging

from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Document

# --- 测试配置 ---
DATABASE_URL = "dm+dmPython://GIMI:DM8DM8DM8@127.0.0.1:5236"

@pytest.fixture(scope="module")
def db_handler():
    """提供一个模块级别的、持久的 DatabaseHandler 实例。"""
    handler = DatabaseHandler(DATABASE_URL)
    return handler

@pytest.fixture(autouse=True)
def setup_and_teardown_table(db_handler: DatabaseHandler):
    """在每个测试函数运行前后，自动清理和重建 `documents` 表。"""
    logging.info("--- (Test Setup) Recreating tables for a clean slate ---")
    db_handler.recreate_tables()
    yield
    logging.info("--- (Test Teardown) Cleaning up tables ---")
    db_handler.recreate_tables()


def test_single_record_commit_succeeds(db_handler: DatabaseHandler):
    """
    基准测试：验证最简单的单条记录插入和提交是成功的。
    """
    with db_handler.get_session() as session:
        doc = Document(file_hash="single_hash", file_path="/path/single.txt", content_slice="", feature_vector="")
        session.add(doc)
        session.commit()
    # 如果没有异常抛出，则测试通过
    assert True


def test_batch_update_with_string_timestamp_workaround_succeeds(db_handler: DatabaseHandler):
    """
    验证变通方案：证明在使用字符串时间戳的变通方案后，
    批量更新 (Batch UPDATE) 现在可以成功执行，不再触发驱动 Bug。
    """
    # 1. 先插入两条记录以便后续更新
    with db_handler.get_session() as session:
        doc1 = Document(file_hash="update_test_1", file_path="/path/update1.txt", content_slice="original_1")
        doc2 = Document(file_hash="update_test_2", file_path="/path/update2.txt", content_slice="original_2")
        session.add_all([doc1, doc2])
        session.commit()
        doc1_id, doc2_id = doc1.id, doc2.id

    # 2. 获取这些记录，修改它们，然后尝试一次性提交更新
    try:
        with db_handler.get_session() as session:
            retrieved_doc1 = session.get(Document, doc1_id)
            retrieved_doc2 = session.get(Document, doc2_id)
            retrieved_doc1.content_slice = "updated_1"
            retrieved_doc2.content_slice = "updated_2"
            # 核心：在循环外提交，这将触发 SQLAlchemy 的工作单元进行批量 UPDATE
            session.commit()
    except Exception as e:
        pytest.fail(f"With the string-timestamp workaround, batch update failed unexpectedly: {e}")

    # 3. 断言数据已被成功更新
    with db_handler.get_session() as session:
        final_doc1 = session.get(Document, doc1_id)
        final_doc2 = session.get(Document, doc2_id)
        assert final_doc1.content_slice == "updated_1"
        assert final_doc2.content_slice == "updated_2"
        logging.info("\nSUCCESS: Batch UPDATE with string-timestamp workaround completed successfully.")


def test_commit_in_loop_succeeds(db_handler: DatabaseHandler):
    """
    验证修复方案：证明在循环内部为每一条记录都单独 commit，可以成功绕过驱动 Bug。
    """
    docs_to_add = [
        Document(file_hash="loop_commit_1", file_path="/path/loop1.txt", content_slice="", feature_vector=""),
        Document(file_hash="loop_commit_2", file_path="/path/loop2.txt", content_slice="", feature_vector="")
    ]
    try:
        with db_handler.get_session() as session:
            for doc in docs_to_add:
                session.add(doc)
                # 核心：在循环内部提交，强制逐一写入
                session.commit()
        # 如果没有异常抛出，则测试通过
        assert True
    except Exception as e:
        pytest.fail(f"Commit-in-loop strategy failed unexpectedly: {e}")
