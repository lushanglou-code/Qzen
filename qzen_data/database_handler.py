# -*- coding: utf-8 -*-
"""
数据库操作模块。

封装了所有与DM8数据库的交互，使用SQLAlchemy作为ORM。
包括数据库连接、会话管理、数据模型的增删改查等。
"""

from contextlib import contextmanager
import logging
from typing import Generator, Optional

from sqlalchemy import create_engine, NullPool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine


class DatabaseHandler:
    """管理数据库连接和会话。"""

    def __init__(self, db_url: str, echo: bool = False):
        """
        初始化 DatabaseHandler。

        此时仅保存配置，不创建实际的数据库引擎，以避免初始化冲突。
        """
        self._db_url: str = db_url
        self._echo: bool = echo
        self._engine: Optional[Engine] = None
        self._session_local: Optional[sessionmaker[Session]] = None

    def _get_engine(self) -> Engine:
        """
        获取数据库引擎，如果不存在则创建。

        这是一个内部方法，确保 create_engine() 只被调用一次。
        """
        if self._engine is None:
            # 真正执行 create_engine 的地方，此时环境已经稳定
            # 根据官方文档，使用 connect_args 传递 dmPython 的特定参数
            connect_args = {
                'connection_timeout': 15  # 设置15秒连接超时
            }
            self._engine = create_engine(
                self._db_url,
                echo=self._echo,
                poolclass=NullPool,
                connect_args=connect_args
            )
        return self._engine

    def _get_session_local(self) -> sessionmaker[Session]:
        """获取会话工厂，如果不存在则创建。"""
        if self._session_local is None:
            self._session_local = sessionmaker(
                autocommit=False, autoflush=False, bind=self._get_engine()
            )
        return self._session_local

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        提供一个上下文管理的数据库会话。

        使用 'with' 语句来确保会话在使用后能被正确关闭。
        """
        session_factory = self._get_session_local()
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def test_connection(self) -> bool:
        """
        测试数据库连接是否成功。

        Returns:
            如果连接成功则返回 True，否则返回 False。
        """
        try:
            # 首次调用时，会触发 _get_engine() 的执行
            engine = self._get_engine()
            with engine.connect() as connection:
                return True
        except Exception as e:
            logging.error(f"数据库连接测试失败: {e}", exc_info=True)
            return False