# -*- coding: utf-8 -*-
"""
数据库操作模块。

封装了所有与DM8数据库的交互，使用SQLAlchemy作为ORM。
包括数据库连接、会话管理、数据模型的增删改查等。
"""

from contextlib import contextmanager
import logging
from typing import Generator, List, Optional

from sqlalchemy import create_engine, NullPool, Text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from .models import Document, Base


class DatabaseHandler:
    """管理数据库连接和会话，并提供数据操作接口。"""

    def __init__(self, db_url: str, echo: bool = False):
        self._db_url: str = db_url
        self._echo: bool = echo
        self._engine: Optional[Engine] = None
        self._session_local: Optional[sessionmaker[Session]] = None

    def _get_engine(self) -> Engine:
        if self._engine is None:
            connect_args = {
                'connection_timeout': 15
            }
            self._engine = create_engine(
                self._db_url,
                echo=self._echo,
                poolclass=NullPool,
                connect_args=connect_args
            )
        return self._engine

    def _get_session_local(self) -> sessionmaker[Session]:
        if self._session_local is None:
            self._session_local = sessionmaker(
                autocommit=False, autoflush=False, bind=self._get_engine()
            )
        return self._session_local

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        session_factory = self._get_session_local()
        session = session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def recreate_tables(self) -> None:
        """清空并重新创建所有数据表，确保一个干净的状态。"""
        engine = self._get_engine()
        logging.info("正在删除所有旧表...")
        Base.metadata.drop_all(bind=engine)
        logging.info("正在创建所有新表...")
        Base.metadata.create_all(bind=engine)

    def test_connection(self) -> bool:
        try:
            engine = self._get_engine()
            with engine.connect():
                return True
        except Exception as e:
            logging.error(f"数据库连接测试失败: {e}", exc_info=True)
            return False

    def get_all_documents(self) -> List[Document]:
        with self.get_session() as session:
            return session.query(Document).all()

    def get_documents_without_vectors(self) -> List[Document]:
        with self.get_session() as session:
            return session.query(Document).filter(Document.feature_vector.is_(None)).all()

    def bulk_insert_documents(self, documents: List[Document]) -> None:
        """高效地批量插入新文档记录。"""
        with self.get_session() as session:
            with session.begin():
                session.bulk_save_objects(documents)
            session.commit()

    def bulk_update_documents(self, documents: List[Document]) -> None:
        """批量更新已存在的文档记录。"""
        with self.get_session() as session:
            with session.begin():
                for doc in documents:
                    session.merge(doc)
            session.commit()
