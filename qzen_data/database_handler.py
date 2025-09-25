# -*- coding: utf-8 -*-
"""
数据库操作模块 (v5.0 - MySQL 迁移)。

此版本根据 v5.0 的架构文档，将数据库后端从 DM8 迁移到 MySQL 8.0。

核心修复：
1.  **废弃所有手动 DDL**: 移除了所有为 DM8 编写的、复杂的、三阶段原子化的
    `recreate_tables` 逻辑。
2.  **恢复标准实践**: 改为使用 SQLAlchemy 官方推荐的、跨数据库兼容的
    `Base.metadata.drop_all()` 和 `Base.metadata.create_all()` 方法。

这使得数据库操作更简洁、更健壮，并完全拥抱新选择的 MySQL 技术栈。
"""

from datetime import datetime, timezone
from contextlib import contextmanager
import logging
import os
from typing import Generator, List, Optional

from sqlalchemy import create_engine, NullPool, StaticPool, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from .models import Base, Document, TaskRun, DeduplicationResult, RenameResult, SearchResult


class DatabaseHandler:
    """
    管理数据库连接和会话，并提供数据操作接口。
    """

    def __init__(self, db_url: str, echo: bool = False):
        """
        初始化 DatabaseHandler。
        """
        self._db_url: str = db_url
        self._echo: bool = echo
        self._engine: Optional[Engine] = None
        self._session_local: Optional[sessionmaker[Session]] = None

    def _get_engine(self) -> Engine:
        """
        获取或创建 SQLAlchemy Engine 实例（懒加载）。
        """
        if self._engine is None:
            engine_opts = {}
            # v5.0 迁移: 移除所有 DM8 特定的连接参数
            connect_args = {}

            if self._db_url.startswith("sqlite:///"):
                engine_opts['poolclass'] = StaticPool
                connect_args['check_same_thread'] = False
            else:
                engine_opts['poolclass'] = NullPool
                connect_args['connect_timeout'] = 15

            self._engine = create_engine(
                self._db_url,
                echo=self._echo,
                connect_args=connect_args,
                **engine_opts
            )
        return self._engine

    def _get_session_local(self) -> sessionmaker[Session]:
        """
        获取或创建 SQLAlchemy Session 工厂（懒加载）。"""
        if self._session_local is None:
            self._session_local = sessionmaker(
                autocommit=False, autoflush=False, bind=self._get_engine()
            )
        return self._session_local

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        提供一个数据库会话的上下文管理器。
        """
        session_factory = self._get_session_local()
        session = session_factory()
        try:
            yield session
        except Exception:
            logging.error("数据库会话发生异常，正在回滚事务。", exc_info=True)
            session.rollback()
            raise
        finally:
            session.close()

    def recreate_tables(self) -> None:
        """
        v5.0 迁移: 使用 SQLAlchemy 标准实践，重建数据库。
        """
        engine = self._get_engine()
        logging.info("正在使用 SQLAlchemy 标准方法初始化数据库...")
        try:
            # 使用 SQLAlchemy 的标准方法，它能正确处理跨数据库的依赖关系
            Base.metadata.drop_all(engine)
            Base.metadata.create_all(engine)
            logging.info("数据库初始化完成，所有表已成功重建。")
        except Exception as e:
            logging.error(f"数据库初始化时发生严重错误: {e}", exc_info=True)
            raise

    def test_connection(self) -> bool:
        """
        测试与数据库的连接是否成功。
        """
        try:
            engine = self._get_engine()
            with engine.connect():
                return True
        except Exception as e:
            logging.error(f"数据库连接测试失败: {e}", exc_info=True)
            return False

    def get_document_by_id(self, doc_id: int) -> Optional[Document]:
        """获取指定 id 的单个 Document 记录。"""
        with self.get_session() as session:
            return session.get(Document, doc_id)

    def get_document_by_path(self, file_path: str) -> Optional[Document]:
        """
        获取指定绝对路径的单个 Document 记录。
        """
        normalized_path = os.path.normpath(file_path)
        with self.get_session() as session:
            return session.query(Document).filter(Document.file_path == normalized_path).first()

    def get_document_by_hash(self, file_hash: str) -> Optional[Document]:
        """
        获取指定内容哈希的单个 Document 记录。
        """
        with self.get_session() as session:
            return session.query(Document).filter(Document.file_hash == file_hash).first()

    def get_documents_by_ids(self, doc_ids: List[int]) -> List[Document]:
        """获取指定 id 列表的多个 Document 记录。"""
        if not doc_ids:
            return []
        with self.get_session() as session:
            return session.query(Document).filter(Document.id.in_(doc_ids)).all()

    def get_all_documents(self) -> List[Document]:
        """
        从数据库中获取所有的 `Document` 记录。
        """
        with self.get_session() as session:
            return session.query(Document).all()

    def get_documents_without_vectors(self) -> List[Document]:
        """
        获取所有尚未计算特征向量的 `Document` 记录。
        """
        with self.get_session() as session:
            return session.query(Document).filter(Document.feature_vector.is_(None)).all()

    def search_documents_by_filename(self, keyword: str) -> List[Document]:
        """根据文件名中的关键词搜索文档。"""
        with self.get_session() as session:
            return session.query(Document).filter(Document.file_path.like(f"%{keyword}%")).all()

    def search_documents_by_content(self, keyword: str) -> List[Document]:
        """
        根据内容切片中的关键词搜索文档。"""
        with self.get_session() as session:
            return session.query(Document).filter(Document.content_slice.like(f"%{keyword}%")).all()

    def bulk_insert_documents(self, documents: List[Document]) -> List[Document]:
        """
        基于内容去重的高效批量插入，并返回新插入的记录。
        """
        if not documents:
            return []

        incoming_hashes = {doc.file_hash for doc in documents}

        with self.get_session() as session:
            existing_hashes_query = session.query(Document.file_hash).filter(Document.file_hash.in_(incoming_hashes))
            existing_hashes = {row[0] for row in existing_hashes_query}
            logging.info(
                f"数据库查询完成，在 {len(incoming_hashes)} 个待插入项中发现 {len(existing_hashes)} 个已存在的哈希。")

        documents_to_insert = [doc for doc in documents if doc.file_hash not in existing_hashes]

        num_duplicates = len(documents) - len(documents_to_insert)
        if num_duplicates > 0:
            logging.info(f"检测到 {num_duplicates} 个内容重复的文档，将跳过插入。")

        if not documents_to_insert:
            logging.info("没有新的文档需要插入。")
            return []

        with self.get_session() as session:
            session.add_all(documents_to_insert)
            session.commit()
            logging.info(f"成功批量插入 {len(documents_to_insert)} 条新文档记录。")

        return documents_to_insert

    def bulk_update_documents(self, documents: List[Document]) -> None:
        """
        v5.0 迁移: 维持逐条更新模式以保证代码一致性。
        """
        if not documents:
            return

        logging.info(f"开始逐一更新 {len(documents)} 条文档记录...")
        updated_count = 0
        for doc_data in documents:
            try:
                with self.get_session() as session:
                    doc_to_update = session.get(Document, doc_data.id)
                    if doc_to_update:
                        if doc_data.file_path:
                            doc_to_update.file_path = doc_data.file_path
                        if doc_data.feature_vector:
                            doc_to_update.feature_vector = doc_data.feature_vector

                        doc_to_update.updated_at = datetime.now(timezone.utc).isoformat()
                        session.commit()
                        updated_count += 1
                    else:
                        logging.warning(f"尝试更新一个不存在的文档 (ID: {doc_data.id})，已跳过。")
            except Exception as e:
                logging.error(f"更新文档 (ID: {doc_data.id}) 时发生严重错误: {e}", exc_info=True)

        logging.info(f"尝试更新 {len(documents)} 条记录，成功更新并提交了 {updated_count} 条。")

    def create_task_run(self, task_type: str) -> TaskRun:
        """
        创建一个新的任务运行记录。
        """
        new_task = TaskRun(task_type=task_type, start_time=datetime.now(timezone.utc).isoformat())
        with self.get_session() as session:
            session.add(new_task)
            session.commit()
            session.refresh(new_task)
        return new_task

    def update_task_summary(self, task_run_id: int, summary: str) -> None:
        """
        更新指定任务运行记录的摘要信息。
        """
        with self.get_session() as session:
            task_run = session.get(TaskRun, task_run_id)
            if task_run:
                task_run.summary = summary
                session.commit()

    def bulk_insert_deduplication_results(self, results: List[DeduplicationResult]) -> None:
        if not results:
            return
        with self.get_session() as session:
            session.add_all(results)
            session.commit()
            logging.info(f"成功批量插入 {len(results)} 条去重结果。")

    def bulk_insert_rename_results(self, results: List[RenameResult]) -> None:
        if not results:
            return
        with self.get_session() as session:
            session.add_all(results)
            session.commit()
            logging.info(f"成功批量插入 {len(results)} 条重命名结果。")

    def bulk_insert_search_results(self, results: List[SearchResult]) -> None:
        if not results:
            return
        with self.get_session() as session:
            session.add_all(results)
            session.commit()
            logging.info(f"成功批量插入 {len(results)} 条搜索结果。")
