# -*- coding: utf-8 -*-
"""
数据库操作模块。

封装了所有与DM8数据库的交互，使用SQLAlchemy Core和ORM功能。
此类旨在成为与数据库交互的唯一入口点，提供了连接管理、会话管理
以及所有数据模型（CURD）的增删改查操作。
"""

import datetime
from contextlib import contextmanager
import logging
from typing import Generator, List, Optional, TypeVar, Iterable

from sqlalchemy import create_engine, NullPool, StaticPool, Text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from .models import Base, Document, TaskRun, DeduplicationResult, RenameResult, SearchResult

# --- 用于分批处理的辅助功能 ---
T = TypeVar('T')
DEFAULT_BATCH_SIZE = 500  # 定义一个默认的批处理大小

def _batch_iterator(iterable: Iterable[T], size: int) -> Generator[List[T], None, None]:
    """将一个可迭代对象切分为多个固定大小的批次。"""
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch

class DatabaseHandler:
    """
    管理数据库连接和会话，并提供数据操作接口。

    此类采用了懒加载模式：SQLAlchemy 的 Engine 和 Session Factory
    只在第一次被请求时才会被创建，这可以避免在应用程序启动时就
    立即建立数据库连接。

    Attributes:
        _db_url (str): 用于连接数据库的URL字符串。
        _echo (bool): 是否在日志中打印所有由 SQLAlchemy 生成的 SQL 语句。
        _engine (Optional[Engine]): SQLAlchemy 的 Engine 对象，是连接池和方言的宿主。
        _session_local (Optional[sessionmaker[Session]]): SQLAlchemy 的会话工厂。
    """

    def __init__(self, db_url: str, echo: bool = False):
        """
        初始化 DatabaseHandler。

        Args:
            db_url: SQLAlchemy 数据库连接 URL。
                    例如: "dm+dmpython://user:password@host:port/database"
            echo: 如果为 True，SQLAlchemy 将记录所有 SQL 语句，默认为 False。
        """
        self._db_url: str = db_url
        self._echo: bool = echo
        self._engine: Optional[Engine] = None
        self._session_local: Optional[sessionmaker[Session]] = None

    def _get_engine(self) -> Engine:
        """
        获取或创建 SQLAlchemy Engine 实例（懒加载）。

        此方法为 DM8 等真实数据库强制指定了 UTF-8 编码，以从根本上
        避免 UnicodeEncodeError。
        """
        if self._engine is None:
            engine_opts = {}
            connect_args = {}

            if self._db_url.startswith("sqlite:///"):
                # 对于内存SQLite，必须在所有操作中使用同一个连接，否则表会丢失。
                engine_opts['poolclass'] = StaticPool
                connect_args['check_same_thread'] = False
            else:
                # 对于真实的、基于网络的数据库，使用NullPool更简单健壮。
                engine_opts['poolclass'] = NullPool
                # --- 关键修复: 根据 dmPython 文档，强制使用 UTF-8 编码 ---
                connect_args['local_code'] = 1  # 1 代表 UTF-8
                connect_args['connection_timeout'] = 15

            self._engine = create_engine(
                self._db_url,
                echo=self._echo,
                connect_args=connect_args,
                **engine_opts
            )
        return self._engine

    def _get_session_local(self) -> sessionmaker[Session]:
        """获取或创建 SQLAlchemy Session 工厂（懒加载）。"""
        if self._session_local is None:
            self._session_local = sessionmaker(
                autocommit=False, autoflush=False, bind=self._get_engine()
            )
        return self._session_local

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        提供一个数据库会话的上下文管理器。

        这是与数据库进行所有交互的标准方式。它能确保会话在使用完毕后
        被正确关闭，并且在发生异常时事务会被回滚。

        使用示例:
            with db_handler.get_session() as session:
                session.query(...).all()

        Yields:
            一个可用的 SQLAlchemy Session 对象。
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
        清空并重新创建所有在 Base.metadata 中定义的表。
        """
        engine = self._get_engine()
        logging.info("正在删除所有旧表...")
        Base.metadata.drop_all(bind=engine)
        logging.info("正在创建所有新表...")
        Base.metadata.create_all(bind=engine)

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

    def bulk_insert_documents(self, documents: List[Document], batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        """
        以分批的方式，高效地批量插入新文档记录，以支持大规模数据处理。

        Args:
            documents: 一个 `Document` 对象的列表。
            batch_size: 每个批次插入的记录数。
        """
        with self.get_session() as session:
            for batch in _batch_iterator(documents, batch_size):
                session.bulk_save_objects(batch)
                session.commit()
            logging.info(f"成功分批插入 {len(documents)} 条文档记录。")

    def bulk_update_documents(self, documents: List[Document], batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        """
        以分批的方式，批量更新已存在的文档记录。

        Args:
            documents: 一个 `Document` 对象的列表。
            batch_size: 每个批次更新的记录数。
        """
        with self.get_session() as session:
            for batch in _batch_iterator(documents, batch_size):
                with session.begin():
                    for doc in batch:
                        session.merge(doc)
                session.commit()
            logging.info(f"成功分批更新 {len(documents)} 条文档记录。")

    def create_task_run(self, task_type: str) -> TaskRun:
        """
        创建一个新的任务运行记录。
        """
        new_task = TaskRun(task_type=task_type, start_time=datetime.datetime.utcnow())
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

    def bulk_insert_deduplication_results(self, results: List[DeduplicationResult], batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        """以分批的方式，批量插入去重结果记录。"""
        with self.get_session() as session:
            for batch in _batch_iterator(results, batch_size):
                session.bulk_save_objects(batch)
                session.commit()
            logging.info(f"成功分批插入 {len(results)} 条去重结果。")

    def bulk_insert_rename_results(self, results: List[RenameResult], batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        """以分批的方式，批量插入重命名结果记录。"""
        with self.get_session() as session:
            for batch in _batch_iterator(results, batch_size):
                session.bulk_save_objects(batch)
                session.commit()
            logging.info(f"成功分批插入 {len(results)} 条重命名结果。")

    def bulk_insert_search_results(self, results: List[SearchResult], batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        """以分批的方式，批量插入搜索结果记录。"""
        with self.get_session() as session:
            for batch in _batch_iterator(results, batch_size):
                session.bulk_save_objects(batch)
                session.commit()
            logging.info(f"成功分批插入 {len(results)} 条搜索结果。")
