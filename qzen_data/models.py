# -*- coding: utf-8 -*-
"""
数据库模型定义模块。

使用 SQLAlchemy 的声明式基类来定义与数据库表映射的Python类。
"""

from sqlalchemy import String, LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有数据模型的基类。"""
    pass


class Document(Base):
    """
    映射到 'documents' 表的 ORM 模型。

    用于存储文档的元数据和计算结果。
    """
    __tablename__ = "documents"

    # 文件哈希值作为主键，确保唯一性
    file_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 文件在中间目录的绝对路径
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    # 存储TF-IDF计算出的特征向量，使用二进制格式
    feature_vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)