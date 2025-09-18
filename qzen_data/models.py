# -*- coding: utf-8 -*-
"""
数据库模型定义模块。

使用 SQLAlchemy 的声明式系统 (Declarative System) 来定义与数据库表
映射的 Python 类。每个类代表一个数据表，类的属性则映射到表的列。
"""

import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
        content_slice (str): 从文档中提取并清洗后的内容切片，用于后续的
                             向量化和内容搜索。提前计算并存储它可以避免
                             重复的文件 I/O 和解析开销。
        feature_vector (str): 文档内容的 TF-IDF 特征向量，以 JSON 字符串的
                            形式存储。选择文本格式而不是二进制格式是为了
                            提高数据库的通用性和可移植性。
    """
    __tablename__ = "documents"

    # 文件内容的 SHA-256 哈希值，作为主键，确保每个唯一文件只被记录一次。
    file_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    
    # 文件在中间文件夹中的绝对、规范化路径。
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    
    # --- 新增字段 ---
    # 存储从文件中提取并清洗后的文本切片，避免重复计算。
    content_slice: Mapped[str] = mapped_column(Text, nullable=True)
    
    # 存储 TF-IDF 计算出的特征向量，使用 JSON 文本格式以保证跨数据库的健壮性。
    # 此字段可以为空，因为向量化是一个独立步骤。
    feature_vector: Mapped[str] = mapped_column(Text, nullable=True)

# --- 新增：任务运行与结果持久化模型 ---

class TaskRun(Base):
    """
    映射到 `task_runs` 表，记录每一次操作任务的运行信息。

    Attributes:
        id (int): 自增主键，作为任务的唯一标识。
        task_type (str): 任务的类型，如 'deduplication', 'rename', 'search'。
        start_time (datetime): 任务开始执行的时间。
        summary (str): 任务完成后的摘要信息，例如处理的文件总数。
    """
    __tablename__ = "task_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    summary: Mapped[str] = mapped_column(Text, nullable=True)

class DeduplicationResult(Base):
    """
    映射到 `deduplication_results` 表，存储去重操作的结果。
    """
    __tablename__ = "deduplication_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_run_id: Mapped[int] = mapped_column(ForeignKey("task_runs.id"))
    duplicate_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_file_hash: Mapped[str] = mapped_column(String(64), nullable=False)

class RenameResult(Base):
    """
    映射到 `rename_results` 表，存储聚类重命名操作的结果。
    """
    __tablename__ = "rename_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_run_id: Mapped[int] = mapped_column(ForeignKey("task_runs.id"))
    original_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    new_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)

class SearchResult(Base):
    """
    映射到 `search_results` 表，存储关键词搜索操作的结果。
    """
    __tablename__ = "search_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_run_id: Mapped[int] = mapped_column(ForeignKey("task_runs.id"))
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    matched_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
