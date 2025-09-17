# -*- coding: utf-8 -*-
"""
数据库操作模块。

封装了所有与DM8数据库的交互，使用SQLAlchemy Core和ORM功能。
此类旨在成为与数据库交互的唯一入口点，提供了连接管理、会话管理
以及所有数据模型（CURD）的增删改查操作。
"""

from contextlib import contextmanager
import logging
from typing import Generator, List, Optional

from sqlalchemy import create_engine, NullPool, Text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from .models import Document, Base


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
        """获取或创建 SQLAlchemy Engine 实例（懒加载）。"""
        if self._engine is None:
            connect_args = {
                # 设置一个连接超时，以避免在数据库无响应时程序无限期等待
                'connection_timeout': 15
            }
            self._engine = create_engine(
                self._db_url,
                echo=self._echo,
                # 使用 NullPool 禁用连接池。对于桌面应用或脚本，每次操作
                # 使用新的连接然后关闭是更简单和健壮的模式，避免了处理
                # 长时间闲置后连接被数据库服务器关闭的问题。
                poolclass=NullPool,
                connect_args=connect_args
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
            # 如果在会话的生命周期内发生任何异常，回滚所有未提交的更改
            logging.error("数据库会话发生异常，正在回滚事务。", exc_info=True)
            session.rollback()
            raise
        finally:
            # 无论成功与否，最终都要关闭会话，将连接交还给（空的）连接池
            session.close()

    def recreate_tables(self) -> None:
        """
        清空并重新创建所有在 Base.metadata 中定义的表。

        这是一个具有高度破坏性的操作，主要用于测试或全新的开始。
        它会删除所有现有数据。
        """
        engine = self._get_engine()
        logging.info("正在删除所有旧表...")
        Base.metadata.drop_all(bind=engine)
        logging.info("正在创建所有新表...")
        Base.metadata.create_all(bind=engine)

    def test_connection(self) -> bool:
        """
        测试与数据库的连接是否成功。

        尝试建立一个连接，如果成功则立即关闭并返回 True。

        Returns:
            如果连接成功，返回 True，否则返回 False。
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

        Returns:
            一个包含所有 `Document` 对象的列表。
        """
        with self.get_session() as session:
            return session.query(Document).all()

    def get_documents_without_vectors(self) -> List[Document]:
        """
        获取所有尚未计算特征向量的 `Document` 记录。

        Returns:
            一个 `Document` 对象列表，其中每个对象的 `feature_vector` 字段为 None。
        """
        with self.get_session() as session:
            return session.query(Document).filter(Document.feature_vector.is_(None)).all()

    def bulk_insert_documents(self, documents: List[Document]) -> None:
        """
        使用 `bulk_save_objects` 高效地批量插入新文档记录。

        Args:
            documents: 一个 `Document` 对象的列表，这些对象将被添加到数据库中。
        """
        with self.get_session() as session:
            # 使用 session.begin() 来确保整个批量操作在一个事务中完成
            with session.begin():
                session.bulk_save_objects(documents)
            session.commit()

    def bulk_update_documents(self, documents: List[Document]) -> None:
        """
        使用 `merge` 批量更新已存在的文档记录。

        `session.merge()` 会根据主键检查记录是否存在。如果存在，则更新；
        如果不存在，则插入。这对于需要同时处理新旧数据的场景很有用。

        Args:
            documents: 一个 `Document` 对象的列表，这些对象将被合并到数据库中。
        """
        with self.get_session() as session:
            with session.begin():
                for doc in documents:
                    session.merge(doc)
            session.commit()
