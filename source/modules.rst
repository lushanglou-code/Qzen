.. _modules:

#########################
代码模块文档 (v5.4)
#########################

本部分由 Sphinx 自动生成，详细记录了 Qzen 项目中每个 Python 模块的 API 和功能。

表现层 (qzen_ui)
================================
.. autosummary::
   :caption: 表现层 (UI)
   :toctree: generated

   qzen_ui.main_window
   qzen_ui.config_dialog
   qzen_ui.worker
   qzen_ui.tabs.setup_tab
   qzen_ui.tabs.processing_tab
   qzen_ui.tabs.analysis_cluster_tab
   qzen_ui.tabs.keyword_search_tab

业务逻辑层 (qzen_core)
====================================
.. autosummary::
   :caption: 业务逻辑层 (Core)
   :toctree: generated

   qzen_core.orchestrator
   qzen_core.ingestion_service
   qzen_core.cluster_engine
   qzen_core.analysis_service
   qzen_core.similarity_engine

数据访问层 (qzen_data)
======================================
.. autosummary::
   :caption: 数据访问层 (DAL)
   :toctree: generated

   qzen_data.database_handler
   qzen_data.file_handler
   qzen_data.models

通用工具包 (qzen_utils)
======================================
.. autosummary::
   :caption: 通用工具包 (Utils)
   :toctree: generated

   qzen_utils.config_manager
   qzen_utils.logger_config
