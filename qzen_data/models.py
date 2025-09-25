# -*- coding: utf-8 -*-
"""
数据库模型定义模块 (v5.2 - 修复 MySQL 索引长度问题)。

此版本通过为 `documents.file_path` 字段移除内联索引并改用带有
`mysql_length=255` 前缀的显式索引，解决了在 MySQL 上因索引键
过长（超过 3072 字节）而导致的 `OperationalError`。
"""

from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """
    所有数据模型的声明式基类。
    """
    pass


class Document(Base):
    """
    映射到 `documents` 数据表的 ORM 模型。
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # v5.2 修复: 移除内联索引，改用带有前缀的显式索引
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_slice: Mapped[str] = mapped_column(Text, nullable=True)
    feature_vector: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Mapped[str] = mapped_column(String(64), default=lambda: datetime.now(timezone.utc).isoformat(), onupdate=lambda: datetime.now(timezone.utc).isoformat())

    # v5.2 修复: 为 file_path 添加带有前缀长度的索引
    __table_args__ = (Index('ix_documents_file_path', 'file_path', mysql_length=255),)

    def __repr__(self):
        return f"<Document(id={self.id}, path='{self.file_path}')>"


# --- 任务运行与结果持久化模型 ---

class TaskRun(Base):
    """
    映射到 `task_runs` 表，记录每一次操作任务的运行信息。
    """
    __tablename__ = "task_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_time: Mapped[str] = mapped_column(String(64), default=lambda: datetime.now(timezone.utc).isoformat())
    summary: Mapped[str] = mapped_column(Text, nullable=True)

class DeduplicationResult(Base):
    """
    映射到 `deduplication_results` 表，存储去重操作的结果。
    """
    __tablename__ = "deduplication_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_run_id: Mapped[int] = mapped_column(ForeignKey("task_runs.id", name="fk_dedup_task_run"))
    duplicate_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_file_hash: Mapped[str] = mapped_column(String(64), nullable=False)

class RenameResult(Base):
    """
    映射到 `rename_results` 表，存储聚类重命名操作的结果。
    """
    __tablename__ = "rename_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_run_id: Mapped[int] = mapped_column(ForeignKey("task_runs.id", name="fk_rename_task_run"))
    original_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    new_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)

class SearchResult(Base):
    """
    映射到 `search_results` 表，存储关键词搜索操作的结果。
    """
    __tablename__ = "search_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_run_id: Mapped[int] = mapped_column(ForeignKey("task_runs.id", name="fk_search_task_run"))
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    matched_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
