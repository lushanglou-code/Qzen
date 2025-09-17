# -*- coding: utf-8 -*-
"""
数据库模型定义模块。

使用 SQLAlchemy 的声明式系统 (Declarative System) 来定义与数据库表
映射的 Python 类。每个类代表一个数据表，类的属性则映射到表的列。
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    所有数据模型的声明式基类。

    SQLAlchemy 的声明式模型都需要继承自一个共同的基类，这个基类
    持有一个 `metadata` 对象，该对象汇集了所有子类定义的表信息。
    """
    pass


class Document(Base):
    """
    映射到 `documents` 数据表的 ORM 模型。

    这张表是程序的核心，用于存储每个唯一文档的元数据和分析结果。

    Attributes:
        file_hash (str): 文档内容的 SHA-256 哈希值。它被用作主键，因为
                       哈希值是内容的唯一标识，可以有效防止同一文件被
                       重复记录。
        file_path (str): 文档在中间文件夹中的绝对路径。此路径是唯一的，
                       用于定位文件以进行内容提取和分析。
        feature_vector (str): 文档内容的 TF-IDF 特征向量，以 JSON 字符串的
                            形式存储。选择文本格式而不是二进制格式是为了
                            提高数据库的通用性和可移植性。
    """
    __tablename__ = "documents"

    # 文件内容的 SHA-256 哈希值，作为主键，确保每个唯一文件只被记录一次。
    file_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    
    # 文件在中间文件夹中的绝对、规范化路径。
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    
    # 存储 TF-IDF 计算出的特征向量，使用 JSON 文本格式以保证跨数据库的健壮性。
    # 此字段可以为空，因为向量化是一个独立步骤。
    feature_vector: Mapped[str] = mapped_column(Text, nullable=True)
