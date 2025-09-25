.. _architecture:

##########################
系统架构设计 (v5.0 - MySQL 迁移)
##########################

本文档详细描述了 Qzen 项目的技术选型、系统架构和关键设计决策。

推荐技术栈
======================

.. list-table:: 技术栈详情
   :widths: 20 20 20 40
   :header-rows: 1

   * - 组件分类
     - 技术选型
     - 建议版本
     - 选型理由
   * - GUI框架
     - PyQt6
     - 6.5+
     - 功能强大、成熟稳定，通过 ``QThread`` 能完美解决UI响应性问题。
   * - 数据持久化/ORM
     - MySQL 8.0
     - 8.0+
     - 业界标准的关系型数据库，社区支持广泛，与 SQLAlchemy 兼容性极佳。
   * - 中文分词
     - Jieba
     - 0.42+
     - 社区广泛使用，分词效果好，支持自定义词典和停用词，满足项目需求。
   * - 相似度计算
     - Scikit-learn
     - 1.3+
     - 提供工业级的TF-IDF和余弦相似度算法，满足“简约高效”的要求。
   * - 应用打包
     - PyInstaller
     - 6.0+
     - 将项目打包为单个 ``.exe`` 文件，便于Windows用户分发和使用。
   * - 文档生成
     - Sphinx
     - 7.0+
     - 遵循DDAC工作流，实现代码与文档的同步。

系统架构
================

(Omitted for brevity...)

关键设计决策
====================

(Omitted for brevity...)

附录：数据库初始化与操作最佳实践 (v5.0)
==================================================

**数据库初始化 (Recreating Tables for MySQL)**

为了确保每次任务运行时都有一个绝对干净的数据库环境，必须在任务开始前彻底清空并重建所有表。在迁移到 MySQL 8.0 后，我们废弃所有为 DM8 数据库制定的复杂手动 DDL 规程。

*   **必须使用标准 DDL 方法**: 数据库表的清空与重建 **必须** 通过调用 SQLAlchemy 核心的 `Base.metadata.drop_all(engine)` 和 `Base.metadata.create_all(engine)` 来完成。这是处理表之间依赖关系的最健壮、最标准的跨数据库方法。

   .. code-block:: python

      # 正确的、兼容 MySQL 的标准表重建方法
      engine = self._get_engine()
      try:
          # 使用 SQLAlchemy 的标准方法，它能正确处理依赖关系
          Base.metadata.drop_all(engine)
          Base.metadata.create_all(engine)
          logging.info("数据库初始化完成，所有表已成功重建。")
      except Exception as e:
          logging.error(f"数据库初始化时发生严重错误: {e}", exc_info=True)
          raise

**数据库操作**

*   **批量插入 (Batch INSERT)**: 对于大批量的数据 **插入**，推荐使用 ``session.add_all(objects)`` 配合单次 ``session.commit()`` 来完成，以获得最佳性能。
*   **批量更新 (Batch UPDATE)**: 与 DM8 不同，MySQL 的驱动程序对批量更新有良好的支持。但为保持代码一致性，我们当前仍维持“逐条处理”的模式。