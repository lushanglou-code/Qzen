# -*- coding: utf-8 -*-
"""
独立的数据库直接操作测试脚本 (v1.2 修正版)。

此版本修正了数据库连接字符串。
"""

import logging
import os
import sys

# --- 路径设置：确保能找到 qzen_data 和 qzen_utils ---
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from qzen_data.database_handler import DatabaseHandler
from qzen_data.models import Document
from qzen_utils.logger_config import setup_logging

# --- 测试配置 ---
# 修正: 使用用户提供的、包含正确大小写和凭据的数据库连接字符串
DATABASE_URL = "dm+dmPython://GIMI:DM8DM8DM8@127.0.0.1:5236"


def main():
    """执行所有数据库操作测试。"""
    setup_logging()
    logging.info(f"--- 开始对数据库进行直接测试 ({DATABASE_URL}) ---")

    db_handler = DatabaseHandler(DATABASE_URL, echo=False)

    # --- 步骤 1: 清理并准备环境 ---
    logging.info("\n[步骤 1/5] 正在清理和重建数据表...")
    try:
        db_handler.recreate_tables()
        logging.info("数据表已成功重建。")
    except Exception as e:
        logging.error(f"重建数据表时发生严重错误，测试中止。错误: {e}", exc_info=True)
        return

    # --- 步骤 2: 测试单条插入和查询 ---
    logging.info("\n[步骤 2/5] 正在测试单条记录插入 (session.add)... ")
    try:
        doc1 = Document(file_hash="single_insert_hash", file_path="/path/single.txt", content_slice="single content", feature_vector="{}")
        with db_handler.get_session() as session:
            session.add(doc1)
            session.commit()
            # 获取由数据库分配的ID
            doc1_id = doc1.id
        
        retrieved_doc = db_handler.get_document_by_id(doc1_id)
        assert retrieved_doc is not None
        assert retrieved_doc.file_hash == "single_insert_hash"
        logging.info("单条记录插入和查询测试... [成功]")
    except Exception as e:
        logging.error(f"单条记录插入和查询测试... [失败] - 错误: {e}", exc_info=True)
        return

    # --- 步骤 3: 测试 add_all() 批量插入 (我们修复后的方法) ---
    logging.info("\n[步骤 3/5] 正在测试 add_all() 批量插入 (我们修复后的方法)... ")
    try:
        docs_to_add = [
            Document(file_hash="add_all_1", file_path="/path/add_all_1.txt", content_slice="", feature_vector=""),
            Document(file_hash="add_all_2", file_path="/path/add_all_2.txt", content_slice="", feature_vector="")
        ]
        db_handler.bulk_insert_documents(docs_to_add)
        all_docs = db_handler.get_all_documents()
        assert len(all_docs) == 3 # 1 (single) + 2 (batch)
        logging.info("add_all() 批量插入测试... [成功]")
    except Exception as e:
        logging.error(f"add_all() 批量插入测试... [失败] - 错误: {e}", exc_info=True)
        return

    # --- 步骤 4: 隔离并确认 bulk_save_objects() 的 Bug ---
    logging.info("\n[步骤 4/5] 正在隔离测试有缺陷的 bulk_save_objects() 方法...")
    docs_for_bug_test = [
        Document(file_hash="bug_test_1", file_path="/path/bug_1.txt"), # content_slice 和 feature_vector 为 None
        Document(file_hash="bug_test_2", file_path="/path/bug_2.txt")
    ]
    try:
        with db_handler.get_session() as session:
            # 直接调用有问题的底层方法
            session.bulk_save_objects(docs_for_bug_test)
            session.commit()
        logging.error("bulk_save_objects() Bug 复现测试... [失败] - 未能捕获到预期的 UnboundLocalError，这意味着驱动行为可能已改变或问题有其他原因。")
    except Exception as e:
        if "cannot access local variable 'str_result'" in str(e):
            logging.info(f"bulk_save_objects() Bug 复现测试... [成功] - 已成功捕获到预期的驱动 Bug: {e}")
        else:
            logging.error(f"bulk_save_objects() Bug 复现测试... [失败] - 捕获到非预期的错误: {e}", exc_info=True)

    # --- 步骤 5: 测试更新和删除 ---
    logging.info("\n[步骤 5/5] 正在测试记录更新与删除...")
    try:
        doc_to_update = db_handler.get_document_by_id(doc1_id)
        doc_to_update.content_slice = "updated content"
        db_handler.bulk_update_documents([doc_to_update])
        
        updated_doc = db_handler.get_document_by_id(doc1_id)
        assert updated_doc.content_slice == "updated content"
        logging.info("记录更新测试... [成功]")

        with db_handler.get_session() as session:
            session.query(Document).delete()
            session.commit()
        final_count = len(db_handler.get_all_documents())
        assert final_count == 0
        logging.info("记录删除测试... [成功]")
    except Exception as e:
        logging.error(f"更新与删除测试... [失败] - 错误: {e}", exc_info=True)

    logging.info("\n--- 所有数据库直接测试已完成 ---")

if __name__ == '__main__':
    main()
