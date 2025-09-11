.. _architecture:

##########################
系统架构设计
##########################

本文档详细描述了 Qzen 项目的技术选型、系统架构和关键设计决策。

推荐技术栈
======================

下表列出了构成Qzen应用程序核心的技术组件及其选型理由：

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
   * - 相似度计算
     - Scikit-learn
     - 1.3+
     - 提供工业级的TF-IDF和余弦相似度算法，满足“简约高效”的要求。
   * - 近邻搜索加速
     - Scikit-learn
     - 1.3+
     - 内置的 ``NearestNeighbors`` 类足以在5000个文档的规模下实现快速搜索。
   * - 应用打包
     - PyInstaller
     - 6.0+
     - 将项目打包为单个 ``.exe`` 文件，便于Windows用户分发和使用。
   * - 文档生成
     - Sphinx
     - 7.0+
     - 遵循DDAC工作流，实现代码与文档的同步。

graphviz_output_format = 'png'

graphviz_dot_args = [ '-Gcharset=utf8'  # <-- 强制 Graphviz 使用 UTF-8 编码处理文本 ]

系统架构
================

本项目采用 **三层分层架构 (3-Tier Architecture)**，将系统解耦为表现层、业务逻辑层和数据访问层。

.. graphviz::
   :align: center

   digraph Architecture {
      // --- 全局字体和编码设置 ---
      graph [fontname="Microsoft YaHei"];
      node  [fontname="Microsoft YaHei"];
      edge  [fontname="Microsoft YaHei"];

      // --- 布局和样式设置 ---
      rankdir=TB;
      node [shape=box, style=rounded];

      // --- 图形内容 ---
      subgraph cluster_ui {
         label = "表现层 (Presentation Layer)";
         ui [label="用户界面 (PyQt6)\n接收用户操作，展示结果"];
      }

      subgraph cluster_core {
         label = "业务逻辑层 (Business Logic Layer)";
         core [label="核心功能模块\n去重、相似度计算、聚类"];
      }

      subgraph cluster_data {
         label = "数据访问层 (Data Access Layer)";
         dal [label="数据访问接口 (SQLAlchemy, os)"];
      }

      subgraph cluster_datasource {
         label = "数据源 (Data Sources)";
         filesystem [label="文件系统"];
         database [label="DM8 数据库"];
      }

      ui -> core [label="调用功能接口"];
      core -> ui [label="返回处理结果 (通过信号)"];
      core -> dal [label="请求数据/文件"];
      dal -> core [label="返回数据"];
      dal -> filesystem;
      dal -> database;
   }

* **表现层 (UI)**: 完全由 ``qzen_ui`` 包负责。它包含所有的窗口、控件和事件处理逻辑，并通过调用业务逻辑层的接口来响应用户交互。
* **业务逻辑层 (Core)**: 由 ``qzen_core`` 包负责。它实现了所有核心算法和业务规则，不依赖于任何UI或具体的数据库实现。
* **数据访问层 (DAL)**: 由 ``qzen_data`` 包负责。它抽象了所有对文件系统和DM8数据库的访问，为上层提供统一、简洁的数据操作接口。

关键设计决策
====================

1.  **UI响应性**: 所有耗时操作（文件扫描、数据库查询、相似度计算） **必须** 在后台线程 (``QThread``) 中执行。主UI线程仅负责更新界面和与用户交互，从而确保界面在处理大量文件时依然流畅。

2.  **轻量级相似度算法**: 我们选择 **TF-IDF + 余弦相似度** 而非深度学习模型（如BERT）。这个决策基于以下考虑：
    * **性能**: 对于5000个文档，该方法计算速度快，资源消耗低，完全满足性能要求。
    * **简单性**: 算法成熟，易于实现和调试。
    * **效果**: 对于文档聚类和相似性排序任务，该方法已经能提供足够好的、可接受的近似结果。

3.  **数据库作为缓存和索引**: DM8数据库不仅用于存储配置，更重要的是作为处理结果的缓存。文档的哈希值、内容切片、特征向量等一旦计算完毕，就会被存储起来。下次运行时，程序会先检查数据库，极大地加速了重复启动和处理的过程。

4.  **面向接口而非实现编程**: 各层之间的交互应通过定义好的接口（例如，业务层的一个类和方法）进行。这使得我们可以轻松地对某一层进行单元测试（例如，使用模拟数据测试业务逻辑层）或在未来进行技术升级。