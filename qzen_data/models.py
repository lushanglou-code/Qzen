# -*- coding: utf-8 -*-
"""
数据库模型定义模块 (v3.3.2 - 驱动兼容性修正)。

此版本将所有时间戳列的类型从 DateTime 更改为 String，并使用 ISO 8601
格式的字符串 (`isoformat()`) 来存储时间。这旨在完全绕过 `sqlalchemy-dm`
驱动中有缺陷的日期时间处理逻辑，从根本上解决 `DatabaseError`。
"""

from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey
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
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    content_slice: Mapped[str] = mapped_column(Text, nullable=True)
    feature_vector: Mapped[str] = mapped_column(Text, nullable=True)  # 存储为 JSON 字符串
    # v3.3.2 修正: 使用 String 类型存储 ISO 格式的时间戳字符串
    created_at: Mapped[str] = mapped_column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Mapped[str] = mapped_column(String, default=lambda: datetime.now(timezone.utc).isoformat(), onupdate=lambda: datetime.now(timezone.utc).isoformat())

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
    # v3.3.2 修正: 使用 String 类型存储 ISO 格式的时间戳字符串
    start_time: Mapped[str] = mapped_column(String, default=lambda: datetime.now(timezone.utc).isoformat())
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
