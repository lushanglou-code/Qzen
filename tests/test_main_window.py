# -*- coding: utf-8 -*-
"""
Qzen 主窗口的UI冒烟测试。

这些测试旨在确保主窗口及其所有核心UI组件能够被成功创建和初始化，
防止在重构或未来开发中意外破坏UI布局。
"""

import pytest
from PyQt6.QtWidgets import QMainWindow

# 假设 pytest 是从项目根目录运行的，并且 qzen_ui 在 PYTHONPATH 中
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
    assert "Qzen (千针)" in app.windowTitle()

def test_tabs_are_created(app: MainWindow):
    """
    测试: 所有标签页是否都已创建并添加到TabWidget中。
    """
    assert app.tabs is not None
    assert app.tabs.count() == 5
    assert app.tabs.tabText(0) == "1. 配置"
    assert app.tabs.tabText(1) == "2. 批量处理"
    assert app.tabs.tabText(2) == "3. 交互式分析"
    assert app.tabs.tabText(3) == "4. 自动整理"
    assert app.tabs.tabText(4) == "5. 关键词搜索"

def test_setup_tab_widgets_exist(app: MainWindow):
    """
    测试: “配置”标签页中的所有控件是否都已创建。
    """
    assert app.db_config_button is not None
    assert app.source_dir_input is not None
    assert app.source_dir_button is not None
    assert app.intermediate_dir_input is not None
    assert app.intermediate_dir_button is not None
    assert app.target_dir_input is not None
    assert app.target_dir_button is not None
    assert app.max_features_spinbox is not None
    assert app.slice_size_spinbox is not None

def test_processing_tab_widgets_exist(app: MainWindow):
    """
    测试: “批量处理”标签页中的所有控件是否都已创建。
    """
    assert app.deduplicate_button is not None
    assert app.vectorize_button is not None
    assert app.deduplication_results_widget is not None

def test_analysis_tab_widgets_exist(app: MainWindow):
    """
    测试: “交互式分析”标签页中的所有控件是否都已创建。
    """
    assert app.load_files_button is not None
    assert app.file_list_widget is not None
    assert app.find_similar_button is not None
    assert app.results_table_widget is not None

def test_organize_tab_widgets_exist(app: MainWindow):
    """
    测试: “自动整理”标签页中的所有控件是否都已创建。
    """
    assert app.similarity_threshold_spinbox is not None
    assert app.cluster_button is not None
    assert app.rename_results_table_widget is not None

def test_keyword_search_tab_widgets_exist(app: MainWindow):
    """
    测试: “关键词搜索”标签页中的所有控件是否都已创建。
    """
    assert app.keyword_input is not None
    assert app.filename_search_button is not None
    assert app.content_search_button is not None
    assert app.keyword_search_results_widget is not None

def test_status_bar_widgets_exist(app: MainWindow):
    """
    测试: 底部状态栏的控件是否都已创建。
    """
    assert app.progress_bar is not None
    assert app.cancel_button is not None
