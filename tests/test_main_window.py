# -*- coding: utf-8 -*-
"""
Qzen 主窗口的UI冒烟测试 (v5.4)。

这些测试旨在确保主窗口能够成功地实例化并集成所有模块化的UI标签页，
并且每个标签页内部的核心控件都已创建。此版本已更新以匹配 v5.x 的 UI 变更。
"""

import pytest
from PyQt6.QtWidgets import QMainWindow

# 假设 pytest 是从项目根目录运行的
from qzen_ui.main_window import MainWindow

@pytest.fixture
def app(qtbot):
    """
    创建一个主窗口实例并注册到qtbot，在测试结束后自动关闭。
    """
    test_app = MainWindow()
    qtbot.addWidget(test_app)
    return test_app

def test_main_window_creation(app: MainWindow):
    """
    测试: 主窗口是否能被成功创建。
    """
    assert isinstance(app, QMainWindow)
    # v5.4 修复: 更新版本号以匹配当前的窗口标题
    assert "Qzen (千针) v5.1" in app.windowTitle()

def test_tabs_are_created_and_named_correctly(app: MainWindow):
    """
    测试: 所有标签页是否都已创建并正确命名。
    """
    assert app.tabs is not None
    assert app.tabs.count() == 4
    assert app.tabs.tabText(0) == "1. 配置"
    assert app.tabs.tabText(1) == "2. 数据摄取"
    assert app.tabs.tabText(2) == "3. 分析与聚类"
    assert app.tabs.tabText(3) == "4. 关键词搜索"

def test_tab_instances_are_created(app: MainWindow):
    """
    测试: MainWindow 是否持有所有模块化 Tab 的实例。
    """
    assert app.setup_tab is not None
    assert app.processing_tab is not None
    assert app.analysis_cluster_tab is not None
    assert app.keyword_search_tab is not None

def test_setup_tab_widgets_exist(app: MainWindow):
    """
    测试: “配置”标签页中的所有控件是否都已创建。
    """
    tab = app.setup_tab
    assert tab.db_config_button is not None
    assert tab.source_dir_input is not None
    assert tab.intermediate_dir_input is not None
    assert tab.target_dir_input is not None
    assert tab.max_features_spinbox is not None
    assert tab.custom_stopwords_input is not None

def test_processing_tab_widgets_exist(app: MainWindow):
    """
    测试: “数据摄取”标签页中的控件是否都已创建。
    """
    tab = app.processing_tab
    assert tab.ingestion_button is not None
    assert tab.results_display is not None

def test_analysis_cluster_tab_widgets_exist(app: MainWindow):
    """
    测试: “分析与聚类”标签页中的控件是否都已创建。
    """
    tab = app.analysis_cluster_tab
    assert tab.cluster_target_dir_line_edit is not None
    assert tab.k_spinbox is not None
    assert tab.similarity_threshold_spinbox is not None
    # v5.4 修复: 检查重构后的 K-Means 和相似度分组按钮
    assert tab.run_kmeans_button is not None
    assert tab.run_similarity_button is not None
    assert tab.source_file_line_edit is not None
    assert tab.find_similar_button is not None
    assert tab.similar_results_table is not None

def test_keyword_search_tab_widgets_exist(app: MainWindow):
    """
    测试: “关键词搜索”标签页中的控件是否都已创建。
    """
    tab = app.keyword_search_tab
    assert tab.keyword_input is not None
    assert tab.filename_search_button is not None
    assert tab.content_search_button is not None
    assert tab.results_table is not None
    assert tab.select_all_checkbox is not None
    assert tab.export_button is not None

def test_status_bar_widgets_exist(app: MainWindow):
    """
    测试: 底部状态栏的控件是否都已创建。
    """
    assert app.progress_bar is not None
    assert app.cancel_button is not None
