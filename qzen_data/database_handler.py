# -*- coding: utf-8 -*-
"""
数据库操作模块 (v3.3.2 - 驱动兼容性修正)。

此版本根据 mcp.json 中更新后的 DB_WRITE_CONSTRAINT 技术规定进行重构，
并解决了 `datetime.utcnow` 的 DeprecationWarning，同时切换到字符串时间戳
以规避数据库驱动的 Bug。
"""

from datetime import datetime, timezone
from contextlib import contextmanager
import logging
import os
from typing import Generator, List, Optional

from sqlalchemy import create_engine, NullPool, StaticPool
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
            connect_args = {}

            if self._db_url.startswith("sqlite:///"):
                engine_opts['poolclass'] = StaticPool
                connect_args['check_same_thread'] = False
            else:
                engine_opts['poolclass'] = NullPool
                connect_args['connection_timeout'] = 15

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
        逐一清空并重新创建所有在 Base.metadata 中定义的、由本程序管理的表。
        """
        engine = self._get_engine()
        logging.info("正在初始化数据库：将逐一清空并重新创建所有相关数据表...")
        tables_to_drop = reversed(Base.metadata.sorted_tables)
        
        logging.info("开始逐一删除旧表...")
        for table in tables_to_drop:
            try:
                table.drop(engine, checkfirst=True)
                logging.info(f"  - 已删除表: {table.name}")
            except Exception as e:
                logging.warning(f"删除表 {table.name} 时出现问题 (可能表原本不存在): {e}")

        logging.info("表删除完成。现在开始逐一创建新表...")
        for table in Base.metadata.sorted_tables:
            try:
                table.create(engine, checkfirst=True)
                logging.info(f"  + 已创建表: {table.name}")
            except Exception as e:
                logging.error(f"创建表 {table.name} 时发生严重错误: {e}", exc_info=True)
                raise
        logging.info("数据库初始化完成，所有表已成功创建。")

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
        v3.2 新增: 获取指定绝对路径的单个 Document 记录。
        """
        normalized_path = os.path.normpath(file_path)
        with self.get_session() as session:
            return session.query(Document).filter(Document.file_path == normalized_path).first()

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
        """根据内容切片中的关键词搜索文档。"""
        with self.get_session() as session:
            return session.query(Document).filter(Document.content_slice.like(f"%{keyword}%")).all()

    def bulk_insert_documents(self, documents: List[Document]) -> None:
        """
        v3.3 优化: 使用 add_all 执行高效的批量插入。
        """
        if not documents:
            return
        with self.get_session() as session:
            session.add_all(documents)
            session.commit()
            logging.info(f"成功批量插入 {len(documents)} 条文档记录。")

    def bulk_update_documents(self, documents: List[Document]) -> None:
        """
        v2.4 最终修正：逐一更新并立即提交，以规避驱动 Bug。
        """
        with self.get_session() as session:
            for doc in documents:
                session.merge(doc)
                session.commit()
            logging.info(f"成功逐一更新 {len(documents)} 条文档记录。")

    def create_task_run(self, task_type: str) -> TaskRun:
        """
        创建一个新的任务运行记录。
        """
        # v3.3.2 修正: 显式地创建一个 ISO 格式的字符串时间戳，以匹配模型。
        # 注意：TaskRun 模型的 `start_time` 字段现在是 String 类型，其 default 参数
        # 在这里不会被触发，因为我们是手动提供 start_time 的值。
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
        """v3.3 优化: 使用 add_all 执行高效的批量插入。"""
        if not results:
            return
        with self.get_session() as session:
            session.add_all(results)
            session.commit()
            logging.info(f"成功批量插入 {len(results)} 条去重结果。")

    def bulk_insert_rename_results(self, results: List[RenameResult]) -> None:
        """
        v3.3 优化: 使用 add_all 执行高效的批量插入。
        """
        if not results:
            return
        with self.get_session() as session:
            session.add_all(results)
            session.commit()
            logging.info(f"成功批量插入 {len(results)} 条重命名结果。")

    def bulk_insert_search_results(self, results: List[SearchResult]) -> None:
        """
        v3.3 优化: 使用 add_all 执行高效的批量插入。
        """
        if not results:
            return
        with self.get_session() as session:
            session.add_all(results)
            session.commit()
            logging.info(f"成功批量插入 {len(results)} 条搜索结果。")
