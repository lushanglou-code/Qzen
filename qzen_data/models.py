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
    """
    pass


class Document(Base):
    """
    映射到 `documents` 数据表的 ORM 模型。
    v2.1 修正版：使用自增整数ID作为主键，并添加时间戳。
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    content_slice: Mapped[str] = mapped_column(Text, nullable=True)
    feature_vector: Mapped[str] = mapped_column(Text, nullable=True)  # 存储为 JSON 字符串
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

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
