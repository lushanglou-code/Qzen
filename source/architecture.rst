.. _architecture:

##########################
系统架构设计 (v3.4)
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
     - SQLAlchemy
     - 2.0+
     - 将业务逻辑与DM8数据库解耦，代码更清晰，易于维护。
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

本项目采用 **三层分层架构 (3-Tier Architecture)**，将系统解耦为表现层、业务逻辑层和数据访问层。该架构确保了各层职责单一，高内聚，低耦合。

.. graphviz::
   :align: center

   digraph Architecture {
      graph [fontname="Microsoft YaHei"];
      node  [fontname="Microsoft YaHei"];
      edge  [fontname="Microsoft YaHei"];
      rankdir=TB;
      node [shape=box, style=rounded];

      subgraph cluster_ui {
         label = "表现层 (Presentation Layer)";
         ui [label="用户界面 (PyQt6)\n接收用户输入，调用业务逻辑层"];
      }

      subgraph cluster_core {
         label = "业务逻辑层 (Business Logic Layer)";
         orchestrator [label="Orchestrator (业务协调器)"];
         analysis_service [label="AnalysisService (分析服务)"];
         cluster_engine [label="ClusterEngine (聚类引擎)"];
      }

      subgraph cluster_data {
         label = "数据访问层 (Data Access Layer)";
         dal [label="DatabaseHandler (数据库操作)"];
      }

      subgraph cluster_datasource {
         label = "数据源 (Data Sources)";
         filesystem [label="文件系统"];
         database [label="DM8 数据库"];
      }

      ui -> orchestrator [label="执行工作流"];
      ui -> analysis_service [label="请求分析数据"];
      orchestrator -> cluster_engine;
      orchestrator -> dal;
      analysis_service -> dal;
      dal -> filesystem;
      dal -> database;
   }

* **表现层 (UI)**: 完全由 ``qzen_ui`` 包负责。它包含所有的窗口、控件和事件处理逻辑。**UI层只与业务逻辑层的服务接口交互，绝不直接访问数据访问层。**
* **业务逻辑层 (Core)**: 由 ``qzen_core`` 包负责。它实现了所有核心算法和业务规则，是整个应用的大脑。
* **数据访问层 (DAL)**: 由 ``qzen_data`` 包负责。它抽象了所有对文件系统和DM8数据库的访问，为上层提供统一、简洁的数据操作接口。

关键设计决策
====================

1.  **UI稳定性高于一切：移除目录树**: 这是在开发 v2.x 版本时得到的、最重要的一条架构经验。最初版本尝试在UI上使用 ``QTreeView`` 来实时展示“中间文件夹”的完整目录结构。然而，当处理数千个文件时，**即使后台数据已成功加载，在渲染UI时依然会导致程序反复出现 ``0xC0000409`` (堆栈溢出) 的致命崩溃**。最终，我们采纳了用户建议，彻底移除了目录树，改为使用标准的 ``QFileDialog`` 来选择操作目录。这个决策从根本上保证了程序在大数据量下的绝对稳定性。

2.  **后台线程与协作式取消**: 所有耗时操作（文件扫描、数据库查询、聚类计算） **必须** 在后台线程 (``QThread``) 中执行，以确保UI的流畅响应。同时，所有后台任务都必须支持协作式取消，允许用户随时安全地中止长时间运行的操作。

3.  **数据库作为唯一事实来源**: DM8数据库是系统的核心。所有文件的元数据、内容摘要和特征向量都必须在“数据摄取”阶段一次性加载到数据库中。后续的所有分析和整理操作都 **只应** 查询数据库，而不是反复进行文件I/O，从而保证了高性能和数据一致性。

4.  **强制单线程访问数据库**: 这是一个关键的稳定性决策，源于社区和实践中发现的 `dmPython` 驱动的线程安全问题。尽管所有耗时任务都在后台线程中运行，但所有与DM8数据库的直接交互都 **必须** 在同一个线程内串行执行，以避免并发访问导致程序无响应或崩溃。

5.  **轻量级相似度算法**: 我们选择 **TF-IDF + 余弦相似度** 而非深度学习模型。这完全满足了项目在个人PC上高效运行的需求，在速度、资源消耗和效果之间取得了最佳平衡。

6.  **可动态更新的自定义停用词**: 为了解决特定领域的高频词污染分析结果的问题，我们实现了一个可运行时动态更新的全局停用词列表。用户在UI上保存新词后，该词会立即对后续的分析任务生效，无需重启程序。

7.  **聚类后自动清理空文件夹**: 为了提升用户体验，在每一轮聚类操作成功执行后，程序会自动从底向上扫描目标文件夹，并删除所有在本次操作中产生的空子文件夹，以保持目录结构的整洁。

8.  **数据摄取阶段的去重与重命名策略**: 为了确保数据库的唯一性并满足文件管理需求，数据摄取（文件扫描）阶段必须执行以下两步去重策略：
    *   **基于内容去重 (Content-based Deduplication)**: 在将文件元数据插入 `documents` 表之前，必须先计算文件的哈希值 (`file_hash`)。通过查询数据库，检查该 `file_hash` 是否已存在。如果存在，则跳过该文件，不进行任何插入操作。这可以防止因内容相同的文件（即使文件名不同）导致 `IntegrityError`，并保证了每个独立内容只在数据库中存储一次。
    *   **基于文件名冲突重命名 (Rename on Filename Conflict)**: 在文件被成功添加到数据库之后（即，其内容是唯一的），需要检查其文件名是否与目标目录中已有的文件冲突。如果一个文件内容不同，但文件名与另一个已处理的文件相同，则必须对其进行重命名（例如，在文件名后附加一个递增的数字或唯一标识符），以避免在最终的文件操作中发生覆盖或混淆。

附录：DM8 数据库交互最佳实践
======================================

在 v3.3 版本的开发中，我们通过集成测试深入研究了 ``sqlalchemy-dm`` 驱动的行为，并总结出了一套兼顾性能与稳定性的数据库操作模式。所有使用 DM8 数据库的项目都应遵循此实践。

问题背景
-----------

``sqlalchemy-dm`` 驱动的 ``do_executemany`` 方法中存在一个 Bug。该 Bug 会在 SQLAlchemy 的工作单元 (Unit of Work) 尝试执行批量 ``UPDATE`` 语句时，触发一个 ``UnboundLocalError`` 异常，导致事务失败。

具体表现
-----------

*   **批量更新 (Batch UPDATE) 失败**: 当会话 (Session) 中包含多个被修改的对象，并在会话结束时调用单次 ``session.commit()`` 时，会触发此 Bug。
*   **批量插入 (Batch INSERT) 成功**: 经过反复测试验证，当会话中包含多个新创建的对象，并使用 ``session.add_all()`` 添加后，调用单次 ``session.commit()`` 是 **安全且高效的**。此场景不会触发 Bug。

最佳实践
-----------

基于以上发现，我们制定了以下强制性规则：

**推荐 (批量插入)**
   对于大批量的数据 **插入**，必须使用 ``session.add_all(objects)`` 配合单次 ``session.commit()`` 来完成，以获得最佳性能。**在构建待插入的对象列表之前，必须先查询数据库，过滤掉那些 `file_hash` 已经存在于 `documents` 表中的文件。** 这样可以从源头上避免 `IntegrityError`。

   .. code-block:: python

      # 正确的批量插入模式
      # 1. 获取所有已存在的哈希值
      with db_handler.get_session() as session:
          existing_hashes = {row[0] for row in session.query(Document.file_hash).all()}

      # 2. 过滤掉已存在的文件，只准备插入新文件
      new_documents_to_insert = []
      for doc_data in all_scanned_files:
          if doc_data['file_hash'] not in existing_hashes:
              new_documents_to_insert.append(Document(**doc_data))

      # 3. 批量插入新文件
      if new_documents_to_insert:
          with db_handler.get_session() as session:
              session.add_all(new_documents_to_insert)
              session.commit() # 在所有对象添加后，单次提交

**禁止 (批量更新)**
   对于 **更新** 已有数据的操作，必须严格遵守“逐条处理”的模式，即在循环中对每个对象单独执行 ``session.merge(obj)`` （或修改属性）和 ``session.commit()``，以规避驱动 Bug。

   .. code-block:: python

      # 正确的逐条更新模式
      with db_handler.get_session() as session:
          for doc in list_of_documents_to_update:
              session.merge(doc)
              session.commit() # 在循环内部，为每个对象单独提交

结论
----

这套模式是在当前 ``sqlalchemy-dm`` 驱动限制下，兼顾性能与稳定性的最佳方案。它允许我们在数据摄取等需要大量插入的场景下获得高性能，同时在更新少量数据时保证绝对的稳定性。
